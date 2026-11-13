"""Recuperação — carga do índice, busca híbrida e montagem da regra vigente.

Carrega o que `ingest/build.py` gravou em `storage/` (índice vetorial e BM25,
os dois persistidos: dentro do container nada é reconstruído a partir de nós em
memória) e responde em quatro passos:

  1. busca híbrida: densa (EmbeddingGemma) + BM25, fundidas por RRF;
  2. reranker cross-encoder (bge-reranker-v2-m3), na GPU quando houver, com o
     material de apoio (FAQ, Manual) sempre depois da norma; vão os 5 primeiros
     trechos de norma, e os artigos que eles citam entram junto;
  3. filtro por data: circular que ainda não vigia ou que já foi revogada sai;
  4. montagem: cada artigo achado volta inteiro e consolidado na data, com a
     redação vigente de cada parte e a fonte marcada (`app/vigencia.py`). Parte
     vigente que a busca não trouxe é completada pelo grafo e registrada em
     `completados` — é a métrica de "busca não trouxe a circular".

Sem data, vale a data de hoje (regra vigente hoje, não a mais recente: uma
eficácia futura não vale antes da sua data).
"""

from __future__ import annotations

import os
import re

# O reranker já está no cache local; sem isto, o huggingface_hub consulta a internet
# a cada carga. Tem de valer antes de qualquer import que carregue o huggingface_hub.
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from dataclasses import dataclass  # noqa: E402
from datetime import date
from functools import cache
from pathlib import Path

from langsmith import traceable
from pydantic import BaseModel, Field

from app import siglas
from app.llm import carregar_env
from app.textos import legivel
from app.vigencia import Grafo

carregar_env()  # liga o LangSmith antes do primeiro @traceable

STORAGE = Path(__file__).resolve().parents[2] / "storage"
DIR_INDICE = STORAGE / "indice"
DIR_BM25 = STORAGE / "bm25"
MANIFESTO = DIR_INDICE / "manifesto.json"
ID_INDICE = "normas"

# Prompts recomendados para o EmbeddingGemma (documento e consulta).
INSTRUCAO_DOCUMENTO = "title: none | text:"
INSTRUCAO_CONSULTA = "task: search result | query:"
RERANKER = "BAAI/bge-reranker-v2-m3"


def criar_embeddings_busca(na_gpu: bool = False):
    from app.llm import criar_embeddings_llamaindex

    return criar_embeddings_llamaindex(na_gpu=na_gpu, query_instruction=INSTRUCAO_CONSULTA,
                                       text_instruction=INSTRUCAO_DOCUMENTO)


def stemmer():
    import Stemmer

    return Stemmer.Stemmer("portuguese")


def construir_bm25(nos):
    """BM25 com vocabulário em ordem fixa.

    O `bm25s` monta o vocabulário a partir de um `set`, cuja ordem muda a cada
    execução do Python: o índice salvo sairia com bytes diferentes a cada build.
    Aqui o vocabulário é reordenado alfabeticamente antes de indexar.
    """
    import bm25s
    from bm25s.tokenization import Tokenized
    from llama_index.core.schema import MetadataMode
    from llama_index.core.vector_stores.utils import node_to_metadata_dict
    from llama_index.retrievers.bm25 import BM25Retriever

    tok = bm25s.tokenize([n.get_content(metadata_mode=MetadataMode.EMBED) for n in nos],
                         stopwords="pt", stemmer=stemmer(), show_progress=False)
    ordem = sorted(tok.vocab)
    novo_id = {tok.vocab[t]: i for i, t in enumerate(ordem)}
    ordenado = Tokenized(ids=[[novo_id[i] for i in doc] for doc in tok.ids],
                         vocab={t: i for i, t in enumerate(ordem)})
    corpus = [node_to_metadata_dict(n) | {"node_id": n.node_id} for n in nos]
    bm25 = bm25s.BM25(corpus=corpus)
    bm25.index(ordenado, show_progress=False)
    return BM25Retriever(existing_bm25=bm25, stemmer=stemmer())


# ---------------------------------------------------------------- saída (Pydantic)
class Trecho(BaseModel):
    id: str
    citacao: str | None = Field(description="sigla do art. 6º; vazio para material de apoio")
    dispositivo: str = Field(description="ART-41, CIRC-02-2026, NT-02, TABELA-URS, FAQ...")
    parte: str = Field(description="caput, § 2º, art. 1, Caso 10, 3.3, linha...")
    cabecalho: str
    texto: str
    contexto: str = ""
    tipo_documento: str
    score: float | None = None


class ParteConsolidada(BaseModel):
    parte: str
    texto: str
    fonte: str = Field(description="ART-n (redação original) ou a circular que deu a redação vigente")


class ArtigoConsolidado(BaseModel):
    dispositivo: str
    cabecalho: str
    abertura_titulo: str
    partes: list[ParteConsolidada]
    fundamentos: list[str] = Field(description="o artigo e as circulares que deram a redação vigente")
    origem: str = Field(default="busca", description="busca | mencionado (citado por um trecho recuperado)")


class Resultado(BaseModel):
    pergunta: str
    data_referencia: date
    trechos: list[Trecho] = Field(description="o que a busca trouxe, já sem circular fora de vigência")
    artigos: list[ArtigoConsolidado] = Field(description="cada artigo achado, inteiro e consolidado na data")
    regras_anexo: list[Trecho] = Field(default_factory=list,
                                       description="regras de aplicação do Anexo IV que acompanham os itens e a "
                                                   "classificação da NT-02 da categoria das linhas da Tabela")
    descartados: list[str] = Field(default_factory=list, description="ids filtrados por vigência")
    completados: list[str] = Field(default_factory=list,
                                   description="redações vigentes que a busca não trouxe e o grafo completou")


# ---------------------------------------------------------------- carga
@dataclass
class Indice:
    vetorial: object
    bm25: object
    nos: dict
    grafo: Grafo


@cache
def carregar() -> Indice:
    from llama_index.core import StorageContext, load_index_from_storage
    from llama_index.retrievers.bm25 import BM25Retriever

    contexto = StorageContext.from_defaults(persist_dir=str(DIR_INDICE))
    # EMBEDDINGS_GPU=1 (opcional): os embeddings da consulta na GPU; o padrão é a CPU, para não disputar a placa
    vetorial = load_index_from_storage(contexto, index_id=ID_INDICE, embed_model=criar_embeddings_busca(
        na_gpu=os.getenv("EMBEDDINGS_GPU", "").strip() == "1"))
    bm25 = BM25Retriever.from_persist_dir(str(DIR_BM25))
    # O persist do BM25Retriever não grava o stemmer: recarregado, ele volta ao inglês, a
    # consulta vira radicais que não existem no índice e toda nota sai 0, sem erro nenhum.
    bm25.stemmer = stemmer()
    nos = dict(contexto.docstore.docs)
    return Indice(vetorial, bm25, nos, Grafo.carregar())


@cache
def reranker():
    """O cross-encoder. Na GPU quando houver (PyTorch com CUDA), carregado direto em meia
    precisão para caber ao lado do gemma4:e4b; na CPU no container, onde o PyTorch é a
    versão só CPU (D11)."""
    import torch
    from sentence_transformers import CrossEncoder

    # RERANKER_DEVICE=cpu força a CPU mesmo com CUDA (deixa a placa toda para o modelo de chat)
    if torch.cuda.is_available() and os.getenv("RERANKER_DEVICE", "").strip().lower() != "cpu":
        return CrossEncoder(RERANKER, device="cuda", model_kwargs={"torch_dtype": torch.float16})
    return CrossEncoder(RERANKER, device="cpu")


def reordenar(pergunta: str, achados, k: int):
    """Reranker lendo o que o modelo vai ler: cabeçalho, contexto e texto.

    O `SentenceTransformerRerank` do LlamaIndex lê só o texto do embedding (sem o
    contexto). Para itens curtos, como "3.3. Acupuntura.", é o parágrafo de abertura
    do grupo que diz que ali se trata de reembolso; com ele, o reranker acerta mais
    (docs/avaliacao_busca.md).
    """
    from llama_index.core.schema import MetadataMode, NodeWithScore

    if not achados:
        return []
    modelo = reranker()
    notas = modelo.predict([(pergunta, a.node.get_content(metadata_mode=MetadataMode.LLM)) for a in achados],
                           show_progress_bar=False)
    ordem = sorted(zip(achados, map(float, notas)), key=lambda x: (-x[1], x[0].node.node_id))
    return [NodeWithScore(node=a.node, score=s) for a, s in ordem[:k]]


# Peso do BM25 na fusão (o da busca densa é 1 − peso). Com 0,5 a RRF ponderada é a RRF
# comum. Escolhido pela avaliação em docs/avaliacao_busca.md: com o reranker lendo o
# contexto, RRF 0,5 teve o melhor acerto no top 5 e o melhor MRR.
PESO_BM25 = 0.5
FUSAO = "rrf"
RRF_K = 60


def candidatos(pergunta: str, n: int = 20):
    """Os n melhores de cada busca, separados: (densa, bm25)."""
    ind = carregar()
    ind.bm25.similarity_top_k = n
    return ind.vetorial.as_retriever(similarity_top_k=n).retrieve(pergunta), ind.bm25.retrieve(pergunta)


def fundir(densa, bm25, peso_bm25: float = PESO_BM25, metodo: str = FUSAO, n: int = 20):
    """Funde as duas listas dando peso `peso_bm25` ao BM25 e 1 − peso à densa.

    rrf      soma de peso / (60 + posição): usa só a ordem de cada lista.
    relativa normaliza as notas de cada lista para 0–1 (mín–máx) e soma ponderado:
             usa também a distância entre as notas.
    """
    from llama_index.core.schema import NodeWithScore

    pesos = ((densa, 1 - peso_bm25), (bm25, peso_bm25))
    total: dict[str, float] = {}
    nos: dict[str, object] = {}
    for lista, peso in pesos:
        if not lista or peso == 0:
            continue
        notas = [a.score or 0.0 for a in lista]
        menor, maior = min(notas), max(notas)
        for pos, a in enumerate(lista, start=1):
            if metodo == "rrf":
                v = peso / (RRF_K + pos)
            else:
                v = peso * ((a.score - menor) / (maior - menor) if maior > menor else 1.0)
            total[a.node.node_id] = total.get(a.node.node_id, 0.0) + v
            nos[a.node.node_id] = a.node
    ordem = sorted(total, key=lambda i: (-total[i], i))[:n]
    return [NodeWithScore(node=nos[i], score=total[i]) for i in ordem]


def norma_primeiro(achados):
    """Regulamento, circulares, NT-02, Anexo IV e Tabela antes do material de apoio.

    FAQ e Manual falam a língua do cliente e por isso ganham na busca, mas não
    fundamentam decisão e perdem para a norma em caso de conflito (art. 5º, §§ 3º e 5º).
    Continuam no resultado, depois da norma, para o modelo entender a pergunta.
    Mantém a ordem do reranker dentro de cada grupo.
    """
    return sorted(achados, key=lambda a: a.node.metadata["tipo_documento"] == "apoio")


# Quantos candidatos cada busca traz e o que vai para o modelo (docs/avaliacao_corte.md e
# docs/experimento_referencias.md). A nota do reranker não é comparável entre perguntas
# (trecho obrigatório já saiu com 0,001 e irrelevante com 0,99), então o corte é por
# posição: os 3 primeiros trechos de norma, e os artigos que eles citam entram junto
# (ver `mencionados`). Com 3 já fechava 30/30 (D14); voltou de 5 para 3 para o modelo
# receber menos texto (D26) e de novo para 5 com as dúvidas reais da rodada 9 (D34: com 3, a
# norma que responde ficava em 4º ou 5º lugar; eval das dúvidas de 59% para 77%).
CANDIDATOS = 40
TOP_NORMA = 5
CORTE_APOIO, MAX_APOIO = 0.5, 2


def cortar(ordenados):
    """Norma: os 3 primeiros. Material de apoio: até 2, com nota ≥ 50% da 1ª de norma,
    sempre depois dela."""
    normas = [a for a in ordenados if a.node.metadata["tipo_documento"] != "apoio"]
    apoio = [a for a in ordenados if a.node.metadata["tipo_documento"] == "apoio"]
    if not normas:
        return apoio[:MAX_APOIO]
    piso = CORTE_APOIO * (normas[0].score or 0.0)
    return normas[:TOP_NORMA] + [a for a in apoio if a.score >= piso][:MAX_APOIO]


# "art. 78", "art. 78, § 1º", "arts. 40 a 42", "arts. 41 e 44"; não "art. 1º desta Circular"
RE_MENCAO = re.compile(r"\barts?\. (\d+)(?!\d)(?!º? desta Circular)º?(?:,? (?:a|e) (\d+))?")


def mencionados(texto: str) -> set[str]:
    """Artigos do Regulamento citados num texto. Intervalo ("arts. 40 a 42") vira os
    artigos do meio, até 6; intervalo maior fica só nas pontas."""
    saida = set()
    for m in RE_MENCAO.finditer(texto):
        ini = int(m[1])
        fim = int(m[2]) if m[2] else ini
        if " a " in m[0] and fim - ini <= 5:
            saida |= {siglas.artigo(n) for n in range(ini, fim + 1)}
        else:
            saida |= {siglas.artigo(ini), siglas.artigo(fim)}
    return saida


def recuperar(pergunta: str, modo: str = "hibrida_rerank", n: int = CANDIDATOS, k: int = 8,
              peso_bm25: float = PESO_BM25, metodo: str = FUSAO):
    """Só a etapa de busca. modo: densa | bm25 | hibrida (devolvem k) | hibrida_rerank
    (devolve o que passa no corte)."""
    densa, bm25 = candidatos(pergunta, n)
    if modo == "densa":
        return densa[:k]
    if modo == "bm25":
        return bm25[:k]
    achados = fundir(densa, bm25, peso_bm25, metodo, n)
    if modo == "hibrida":
        return achados[:k]
    return cortar(norma_primeiro(reordenar(pergunta, achados, n)))


# ---------------------------------------------------------------- filtro e montagem
def _vigente(meta: dict, dia: date) -> bool:
    """Circular só vale entre o início de vigência e a revogação (art. 5º, § 1º)."""
    inicio, fim = meta.get("vigencia_inicio"), meta.get("vigencia_fim")
    if meta.get("tipo_documento") != "circular":
        return True
    return date.fromisoformat(inicio) <= dia and not (fim and dia >= date.fromisoformat(fim))


def _trecho(n, score=None) -> Trecho:
    m = n.metadata
    return Trecho(id=n.id_, citacao=m["citacao"] or None, dispositivo=m["dispositivo"], parte=m["parte"],
                  cabecalho=m["cabecalho"], texto=n.text,
                  contexto=m.get("contexto", ""), tipo_documento=m["tipo_documento"], score=score)


def _alvos(meta: dict) -> list[str]:
    """Artigos do Regulamento que um chunk de circular altera."""
    return sorted({p.split()[1] for p in meta.get("relacoes", "").split("; ")
                   if p.startswith(("altera ", "revoga_parte ", "eficacia_futura "))}, key=siglas.numero_artigo)


def consolidar(dispositivo: str, dia: date, ind: Indice, vistos: set[str]) -> tuple[ArtigoConsolidado, list[str]]:
    """O artigo inteiro na data: cada parte na redação vigente, com a fonte."""
    originais = {n.metadata["parte"]: n for n in ind.nos.values()
                 if n.metadata["tipo_documento"] == "regulamento" and n.metadata["dispositivo"] == dispositivo}
    revogadas = {r.parte for r in ind.grafo.revogacoes_de_parte
                 if r.dispositivo == dispositivo and r.inicio <= dia}
    nomes = list(originais) + [p for p in ind.grafo.partes_alteradas(dispositivo) if p not in originais]
    partes, completados = [], []
    for parte in nomes:
        if parte in revogadas:
            continue
        red = ind.grafo.redacao(dispositivo, parte, dia)
        if red.fonte == dispositivo:
            partes.append(ParteConsolidada(parte=parte, texto=originais[parte].text, fonte=dispositivo))
            continue
        partes.append(ParteConsolidada(parte=parte, texto=legivel(red.texto or ""), fonte=red.fonte))
        if red.fonte not in vistos:
            completados.append(f"{dispositivo} {parte} <- {red.fonte}")
    exemplo = next(iter(originais.values()))
    cab = exemplo.metadata["cabecalho"].rsplit(" — ", 1)[0] + f" — Art. {siglas.numero_artigo(dispositivo)}"
    fund = ind.grafo.fundamentos(dispositivo, dia, partes=[p.parte for p in partes])
    return (ArtigoConsolidado(dispositivo=dispositivo, cabecalho=cab, abertura_titulo=exemplo.metadata["contexto"],
                              partes=partes, fundamentos=fund), completados)


def para_prompt(r: Resultado) -> str:
    """O resultado da busca como texto para o modelo: artigos consolidados primeiro (com a
    fonte de cada parte), depois os demais trechos de norma, as regras do Anexo IV e o
    material de apoio, marcado como não citável."""
    blocos = []
    for a in r.artigos:
        partes = "\n".join(f"{p.texto} [{p.fonte}]" for p in a.partes)
        origem = " (citado por outro trecho)" if a.origem == "mencionado" else ""
        blocos.append(f"### {a.cabecalho}{origem}\nCitar: {', '.join(a.fundamentos)}\n"
                      f"Contexto do título: {a.abertura_titulo}\n{partes}")
    consolidados = {a.dispositivo for a in r.artigos}
    fundamentos = {f for a in r.artigos for f in a.fundamentos}
    for t in r.trechos:
        if t.tipo_documento == "regulamento" and t.dispositivo in consolidados:
            continue   # já está no artigo consolidado
        if t.tipo_documento == "circular" and t.citacao in fundamentos and "altera" in t.cabecalho:
            continue   # a redação que ela deu já entrou no artigo consolidado
        rotulo = "NÃO CITÁVEL (material de apoio)" if not t.citacao else f"Citar: {t.citacao}"
        contexto = f"\nContexto: {t.contexto}" if t.contexto else ""
        blocos.append(f"### {t.cabecalho}\n{rotulo}{contexto}\n{t.texto}")
    for t in r.regras_anexo:
        blocos.append(f"### {t.cabecalho}\nCitar: {t.citacao}\n{t.texto}")
    return f"Data de referência: {r.data_referencia:%d/%m/%Y}\n\n" + "\n\n".join(blocos)


@traceable(name="buscar_normas", run_type="retriever")
def buscar(pergunta: str, data_referencia: date | None = None) -> Resultado:
    from app.datas import hoje

    dia = data_referencia or hoje()
    ind = carregar()
    achados = recuperar(pergunta, "hibrida_rerank")

    trechos, descartados = [], []
    for a in achados:
        (trechos if _vigente(a.node.metadata, dia) else descartados).append(a)
    vistos = {a.node.metadata["citacao"] for a in trechos}

    artigos: list[str] = []
    for a in trechos:
        m = a.node.metadata
        alvos = [m["dispositivo"]] if m["tipo_documento"] == "regulamento" else _alvos(m)
        artigos += [x for x in alvos if x not in artigos]
    # Artigos citados pelos trechos de norma entram junto, buscados pelo número (um nível).
    # As menções feitas dentro de circulares ficam de fora: o artigo que a circular altera
    # já entrou acima, e o resto é fecho padrão ("na forma do seu art. 5º... art. 6º, II").
    existentes = {n.metadata["dispositivo"] for n in ind.nos.values() if n.metadata["tipo_documento"] == "regulamento"}
    mencoes: list[str] = []
    for a in trechos:
        if a.node.metadata["tipo_documento"] in ("apoio", "circular"):
            continue
        novos = sorted(mencionados(a.node.text) & existentes, key=siglas.numero_artigo)
        mencoes += [x for x in novos if x not in artigos and x not in mencoes]
    consolidados, completados = [], []
    for art in artigos + mencoes:
        c, falt = consolidar(art, dia, ind, vistos)
        c.origem = "mencionado" if art in mencoes else "busca"
        consolidados.append(c)
        completados += falt

    # Regras de aplicação do Anexo IV acompanham qualquer item dele (11.2 só o grupo 3).
    grupos = {a.node.metadata.get("grupo") for a in trechos if a.node.metadata["tipo_documento"] == "anexo"}
    regras = [_trecho(n) for n in ind.nos.values() if n.metadata["tipo_documento"] == "anexo_regra"
              and grupos and (n.metadata["aplica_a"] == "todos" or n.metadata["aplica_a"] in grupos)]
    # A linha da Tabela traz a categoria do procedimento; a classificação dela na NT-02 (Anexo A) diz o regime que
    # se aplica e entra junto, como os artigos citados (D55). Sem ela, a pergunta "o relatório cobrado à parte é
    # reembolsável?" recebia só a regra do relatório que sana pendência, e a resposta dizia que não era.
    # a Tabela escreve a categoria pelo nome ("Relatório clínico"); a NT-02, pelo código e pelo nome
    # ("RELATORIO_CLINICO — Relatório clínico."). Só o OPME tem nome diferente nas duas.
    categorias = {{"Material / OPME": "Material, órtese, prótese ou material especial"}.get(c, c)
                  for a in trechos if a.node.metadata["tipo_documento"] == "tabela"
                  and (c := a.node.metadata.get("categoria_tabela"))}
    ja = {a.node.node_id for a in trechos}
    regras += [_trecho(n) for n in ind.nos.values() if n.node_id not in ja and n.metadata["tipo_documento"] == "nota_tecnica"
               and n.metadata["parte"].startswith("3.1 ") and n.text.split(" — ", 1)[-1].split(".")[0] in categorias]

    return Resultado(pergunta=pergunta, data_referencia=dia,
                     trechos=[_trecho(a.node, a.score) for a in trechos], artigos=consolidados,
                     regras_anexo=regras, descartados=[a.node.id_ for a in descartados],
                     completados=completados)

"""Corta a kb/ em chunks pela unidade da norma, com metadados (docs/estrategia_chunking.md).

    python -m ingest.chunking          # resumo por documento, sem gravar nada

Cada chunk é um `TextNode` do LlamaIndex com três camadas de texto:
  * `cabecalho` — origem curta ("Regulamento Geral — Título II — ... — Art. 11, caput").
    Entra no embedding e no BM25, junto com o texto.
  * texto — o dispositivo em si.
  * `contexto` — parágrafo de abertura do título, do grupo do Anexo IV ou a ementa
    da circular, na íntegra. Não entra no embedding (não dilui trechos curtos);
    vai para o modelo junto com o chunk.

Os demais metadados (citação, dispositivo, parte, vigência...) servem ao filtro por
data e à citação, e ficam fora do texto que vira embedding.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path

import docx
import pymupdf
from llama_index.core.schema import MetadataMode, TextNode

from app import siglas
from app.textos import legivel
from ingest import regulamento
from ingest.circulares import DECLARACOES, artigos_da_circular
from ingest.grafo_normativo import texto_normalizado

RAIZ = Path(__file__).resolve().parents[1]
KB = RAIZ / "kb"

RE_CABECALHO_PAG = re.compile(r"\n[^\n]*\nSaúdeMais Saúde Suplementar S\.A\. — documento normativo\npág\. \d+\n")

# Metadados que não entram no texto do embedding nem no BM25.
SO_FILTRO = ["arquivo", "tipo_documento", "citacao", "citavel", "dispositivo", "parte",
             "vigencia_inicio", "vigencia_fim", "relacoes", "grupo", "aplica_a", "categoria_tabela"]


def _limpa(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


def _texto_pdf(nome: str) -> str:
    """Texto do PDF sem os cabeçalhos e rodapés de página, mantendo as quebras de linha."""
    texto = "\n" + "".join(p.get_text() for p in pymupdf.open(KB / nome))
    return RE_CABECALHO_PAG.sub("\n", texto)


def no(texto: str, cabecalho: str, *, arquivo: str, tipo_documento: str, citacao: str | None,
       contexto: str = "", **meta) -> TextNode:
    """Um chunk. O id vem do conteúdo: o mesmo texto gera o mesmo id em todo build."""
    texto = legivel(_limpa(texto))
    chave = f"{arquivo}|{cabecalho}|{texto}"
    no_ = TextNode(
        id_=f"{citacao or arquivo}#{hashlib.sha256(chave.encode()).hexdigest()[:16]}",
        text=texto,
        metadata={"cabecalho": cabecalho, "contexto": contexto, "arquivo": arquivo,
                  "tipo_documento": tipo_documento, "citacao": citacao or "",
                  "citavel": citacao is not None, **meta},
        excluded_embed_metadata_keys=["contexto", *SO_FILTRO],
        excluded_llm_metadata_keys=SO_FILTRO,
        metadata_template="{value}", metadata_separator="\n",
        text_template="{metadata_str}\n\n{content}",
    )
    return no_


# ------------------------------------------------------------------ Regulamento
def chunks_regulamento() -> list[TextNode]:
    """Um chunk por parte de artigo (caput, cada §, parágrafo único)."""
    est = regulamento.estrutura()
    nos = []
    for art, partes in regulamento.artigos().items():
        onde = est["artigos"][art]
        titulo = est["titulos"][onde["titulo"]]
        caminho = [f"Título {onde['titulo'].split()[1]} — {titulo['nome']}"] + ([onde["capitulo"]] if onde["capitulo"] else [])
        for parte, texto in partes.items():
            rotulo = f"Art. {siglas.numero_artigo(art)}, {parte}"
            nos.append(no(texto, " — ".join(["Regulamento Geral", *caminho, rotulo]),
                          arquivo="regulamento_geral.pdf", tipo_documento="regulamento",
                          citacao=art, contexto=titulo["abertura"], dispositivo=art, parte=parte,
                          vigencia_inicio="", vigencia_fim=""))
    return nos


# ------------------------------------------------------------------ Circulares
def chunks_circulares(grafo: dict) -> list[TextNode]:
    """Um chunk por artigo da circular, com o que ele faz (declarado em ingest/circulares.py)."""
    revogada_em = {r["alvo"]: c["inicio_vigencia"] for c in grafo["circulares"]
                   for r in c["relacoes"] if r["tipo"] == "revoga"}
    ementas = {c["sigla"]: c["ementa"] or "" for c in grafo["circulares"]}
    nos = []
    for sigla, decl in DECLARACOES.items():
        _, num, ano = sigla.split("-")
        artigos = artigos_da_circular(texto_normalizado(KB / decl["arquivo"]))
        for n, texto in artigos.items():
            relacoes = decl["artigos"].get(n, [])
            faz = "; ".join(f"{t} {a}" + (f" {p}" if p else "") for t, a, p, *_ in relacoes)
            cab = f"Circular Normativa {num}/{ano} — vigência a partir de {decl['vigencia']} — Art. {n}"
            if faz:
                cab += f" — {faz}"
            nos.append(no(texto, cab, arquivo=decl["arquivo"], tipo_documento="circular",
                          citacao=sigla, contexto=f"Ementa: {ementas[sigla]}", dispositivo=sigla,
                          parte=f"art. {n}", vigencia_inicio=decl["vigencia"],
                          vigencia_fim=revogada_em.get(sigla, ""), relacoes=faz))
    return nos


# ------------------------------------------------------------------ Tabela URS
def chunks_tabela(tabela: dict) -> list[TextNode]:
    """Um chunk por código (sem o teto: o teto vem do cadastro, resolvido na data) e
    um por seção de texto da tabela (valor da URS, conversão, notas, observações)."""
    nos = []
    for linha in tabela["linhas"]:
        obs = linha["nota"] or linha["observacao"]
        texto = f"{linha['descricao']}. Categoria: {linha['categoria_tabela']}." + (f" Observação: {obs}" if obs else "")
        nos.append(no(texto, f"Tabela URS 2026 — {linha['codigo']}", arquivo="tabela_urs_2026.pdf",
                      tipo_documento="tabela", citacao=linha["codigo"], dispositivo=linha["codigo"],
                      parte="linha", categoria_tabela=linha["categoria_tabela"],
                      vigencia_inicio=tabela["vigencia_inicio"], vigencia_fim=tabela["vigencia_fim"]))

    texto = _limpa(_texto_pdf("tabela_urs_2026.pdf"))
    inicio = texto[texto.index("1. Valor da Unidade"):texto.index("Código TUSS Descrição")]
    fim = texto[texto.index("4. Notas da tabela"):]
    # "(1) O teto..." abre nota; "nota (1) da seção" é só remissão
    secoes = re.split(r" (?=[1-6]\. [A-ZÁÉÍÓÚ]|\(\d\) [A-Z]|5\.\d\. |Tabela publicada)", inicio + " " + fim)
    for s in secoes:
        s = s.strip()
        if len(s) < 30:
            continue
        rotulo = re.match(r"(\d\.\d\.|\d\.|\(\d\)|Tabela publicada)", s)[0]
        nos.append(no(s, f"Tabela URS 2026 — {rotulo}", arquivo="tabela_urs_2026.pdf",
                      tipo_documento="tabela", citacao=None, dispositivo="TABELA-URS", parte=rotulo,
                      vigencia_inicio=tabela["vigencia_inicio"], vigencia_fim=tabela["vigencia_fim"]))
    return nos


# ------------------------------------------------------------------ Nota Técnica 02
def chunks_nota_tecnica() -> list[TextNode]:
    """Linhas das tabelas (campos C1–C10, pendências P01–P35) e itens numerados e casos
    do texto, cada um com o título da seção."""
    arquivo, sigla = "nota_tecnica_02_documentos.pdf", siglas.nota_tecnica(2)
    doc = pymupdf.open(KB / arquivo)
    nos, partes_texto = [], []
    for pagina in doc:
        tabelas = pagina.find_tables().tables
        for t in tabelas:
            linhas = t.extract()
            cab = [_limpa(c or "").replace("Ca mpo", "Campo") for c in linhas[0]]
            for linha in linhas[1:]:
                cel = [_limpa(c or "") for c in linha]
                if not cel[0]:
                    continue
                secao = ("2. Campos obrigatórios do documento fiscal" if cel[0].startswith("C")
                         else "5. Anexo B — Códigos de pendência documental")
                texto = ". ".join(f"{k}: {v.rstrip('.')}" for k, v in zip(cab, cel) if v and v != "—") + "."
                nos.append(no(texto, f"Nota Técnica 02 — {secao} — {cel[0]}", arquivo=arquivo,
                              tipo_documento="nota_tecnica", citacao=sigla, dispositivo=sigla, parte=cel[0],
                              vigencia_inicio="", vigencia_fim=""))
        # texto fora das tabelas, para não duplicar as linhas
        caixas = [pymupdf.Rect(t.bbox) for t in tabelas]
        for b in pagina.get_text("blocks"):
            r = pymupdf.Rect(b[:4])
            if any(r.intersects(c) for c in caixas) or b[4].startswith(("Nota Técnica 02 —", "SaúdeMais", "pág.")):
                continue
            partes_texto.append(b[4])
    texto = "\n" + "".join(partes_texto)
    texto = re.sub(r"\n[^\n]*SaúdeMais Saúde Suplementar S\.A\. — documento normativo\n", "\n", texto)

    marcas = list(re.finditer(r"\n(?:(\d+)\. ([A-ZÁÉÍÓÚ][^\n]*)|(\d+\.\d+)\. |(Caso \d+)\. )", texto))
    secao, abertura = "", {}
    for i, m in enumerate(marcas):
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        corpo = _limpa(texto[m.end():fim])
        if m[1]:  # título de seção; o texto até o primeiro item é a abertura da seção
            secao = f"{m[1]}. {_limpa(m[2])}"
            abertura[secao] = corpo
            continue
        rotulo = m[3] or m[4]
        # O Anexo A (3.1) lista as 7 categorias com o regime de cada uma: um chunk por categoria.
        categorias = re.split(r" (?=[A-Z_]{6,} — )", corpo)
        if len(categorias) > 1:
            for cat in categorias[1:]:
                nome = cat.split(" — ")[0]
                nos.append(no(cat, f"Nota Técnica 02 — {secao} — {nome}", arquivo=arquivo,
                              tipo_documento="nota_tecnica", citacao=sigla, contexto=categorias[0],
                              dispositivo=sigla, parte=f"{rotulo} {nome}", vigencia_inicio="", vigencia_fim=""))
            continue
        nos.append(no(f"{rotulo}. {corpo}", f"Nota Técnica 02 — {secao} — {rotulo}", arquivo=arquivo,
                      tipo_documento="nota_tecnica", citacao=sigla, contexto=abertura.get(secao, ""),
                      dispositivo=sigla, parte=rotulo, vigencia_inicio="", vigencia_fim=""))
    return nos


# ------------------------------------------------------------------ Anexo IV
def chunks_anexo_iv() -> list[TextNode]:
    """Um chunk por item de exclusão, com o grupo no cabeçalho e o parágrafo de abertura do
    grupo no contexto. O item 11 são regras de aplicação, não exclusões."""
    arquivo, sigla = "anexo_iv_exclusoes.pdf", siglas.anexo("IV")
    texto = _texto_pdf(arquivo)
    preambulo = _limpa(texto[texto.index("Este Anexo é parte"):texto.index("\n1. ")])
    texto = texto[texto.index("\n1. "):texto.index("Publicado em")]
    marcas = list(re.finditer(r"\n(?:(\d+)\. ([A-ZÁÉÍÓÚ][^\n]*)(?=\n)|(\d+)\.(\d+)\. )", texto))
    nos = [no(preambulo, "Anexo IV — Exclusões de cobertura — abertura", arquivo=arquivo,
              tipo_documento="anexo", citacao=sigla, dispositivo=sigla, parte="abertura",
              grupo="", aplica_a="todos", vigencia_inicio="", vigencia_fim="")]
    grupo, nome, abertura = "", "", ""
    for i, m in enumerate(marcas):
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        corpo = _limpa(texto[m.end():fim])
        if m[1]:
            grupo, nome, abertura = m[1], _limpa(m[2]), corpo
            continue
        item = f"{m[3]}.{m[4]}"
        if nome == "Regras de aplicação":
            # 11.2 trata só do grupo 3; as demais valem para o anexo inteiro
            alvo = re.search(r"casos do grupo (\d+)", corpo)
            nos.append(no(f"{item}. {corpo}", f"Anexo IV — {grupo}. {nome} — {item}", arquivo=arquivo,
                          tipo_documento="anexo_regra", citacao=sigla, contexto=preambulo, dispositivo=sigla,
                          parte=item, grupo=grupo, aplica_a=alvo[1] if alvo else "todos",
                          vigencia_inicio="", vigencia_fim=""))
            continue
        nos.append(no(f"{item}. {corpo}", f"Anexo IV — Grupo {grupo} — {nome} — item {item}", arquivo=arquivo,
                      tipo_documento="anexo", citacao=sigla, contexto=abertura, dispositivo=sigla,
                      parte=item, grupo=grupo, aplica_a=grupo, vigencia_inicio="", vigencia_fim=""))
    return nos


# ------------------------------------------------------------------ Manual (material de apoio)
def paragrafos_manual() -> list[str]:
    """Parágrafos do Manual, juntando o que a quebra de página cortou."""
    paragrafos: list[str] = []
    for pagina in pymupdf.open(KB / "manual_rede_credenciada.pdf"):
        for b in pagina.get_text("blocks"):
            t = _limpa(b[4])
            if not t or t.isupper() or t.startswith(("Manual da Rede Credenciada e do Reembolso",
                                                     "SaúdeMais Saúde", "pág.")):
                continue
            if paragrafos and not paragrafos[-1].endswith((".", ":", "?", "!")):
                paragrafos[-1] += " " + t
            else:
                paragrafos.append(t)
    return paragrafos


def chunks_manual() -> list[TextNode]:
    return [no(p, f"Manual da Rede Credenciada (material de apoio, não fundamenta decisão) — parágrafo {i}",
               arquivo="manual_rede_credenciada.pdf", tipo_documento="apoio", citacao=None,
               dispositivo="MANUAL", parte=f"§{i}", vigencia_inicio="", vigencia_fim="")
            for i, p in enumerate(paragrafos_manual(), start=1)]


# ------------------------------------------------------------------ FAQ (material de apoio)
def chunks_faq() -> list[TextNode]:
    """Um chunk por pergunta e resposta. O próprio FAQ avisa que pode estar desatualizado."""
    d = docx.Document(KB / "faq_interno.docx")
    aviso = ("FAQ interno, última revisão de agosto de 2025: pode estar desatualizado e não "
             "fundamenta decisão; em conflito, prevalecem as circulares e o Regulamento (art. 5º, §§ 3º e 5º).")
    nos, secao, pergunta, resposta, n = [], "", None, [], 0

    def fecha():
        nonlocal n
        if pergunta:
            n += 1
            nos.append(no(f"Pergunta: {pergunta} Resposta: {' '.join(resposta)}",
                          f"FAQ interno (pode estar desatualizado) — {secao}", arquivo="faq_interno.docx",
                          tipo_documento="apoio", citacao=None, contexto=aviso, dispositivo="FAQ",
                          parte=f"P{n}", vigencia_inicio="", vigencia_fim=""))

    for p in d.paragraphs:
        if p.style.name == "Heading 1":
            fecha(); pergunta, resposta, secao = None, [], p.text.strip()
        elif p.text.strip() and any(r.bold for r in p.runs):
            fecha(); pergunta, resposta = p.text.strip(), []
        elif pergunta and p.text.strip():
            resposta.append(p.text.strip())
    fecha()
    return nos


def todos(grafo: dict, tabela: dict) -> list[TextNode]:
    return (chunks_regulamento() + chunks_circulares(grafo) + chunks_tabela(tabela)
            + chunks_nota_tecnica() + chunks_anexo_iv() + chunks_manual() + chunks_faq())


if __name__ == "__main__":
    import json

    g = json.loads((RAIZ / "storage" / "grafo_normativo.json").read_text(encoding="utf-8"))
    t = json.loads((RAIZ / "storage" / "tabela_urs.json").read_text(encoding="utf-8"))
    nos = todos(g, t)
    print(Counter(n.metadata["arquivo"] for n in nos))
    ids = [n.id_ for n in nos]
    print(len(nos), "chunks;", len(set(ids)), "ids distintos")
    for n in nos[:1] + [x for x in nos if x.metadata["parte"] in ("3.3", "11.2", "art. 1", "C8", "Caso 13")][:6]:
        print("-----", n.id_)
        print(n.get_content(metadata_mode=MetadataMode.EMBED)[:300])

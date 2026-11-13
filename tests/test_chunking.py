"""Declaração das circulares, chunks e montagem do artigo consolidado.

Nada aqui chama o Ollama: o índice é lido de storage/ e a montagem usa o grafo.
"""

import copy
from datetime import date

import pytest

from app.rag import _vigente, carregar, consolidar
from ingest import circulares, grafo_normativo


# ------------------------------------------------------------ declaração das circulares
def test_declaracao_errada_para_o_build(monkeypatch):
    errada = copy.deepcopy(circulares.DECLARACOES)
    errada["CIRC-02-2026"]["artigos"][3] = [("altera", "ART-45", "caput")]   # o art. 3º fala do art. 44
    monkeypatch.setattr(grafo_normativo, "DECLARACOES", errada)
    with pytest.raises(grafo_normativo.DeclaracaoDivergente, match="não menciona ART-45"):
        grafo_normativo.extrair_circular("CIRC-02-2026", errada["CIRC-02-2026"])


def test_vigencia_declarada_diferente_do_pdf_para_o_build():
    errada = copy.deepcopy(circulares.DECLARACOES["CIRC-11-2026"])
    errada["vigencia"] = "2026-03-01"
    with pytest.raises(grafo_normativo.DeclaracaoDivergente, match="vigência declarada"):
        grafo_normativo.extrair_circular("CIRC-11-2026", errada)


# ------------------------------------------------------------ chunks
@pytest.fixture(scope="module")
def ind():
    return carregar()


def test_ids_unicos_e_citacoes_validas(ind):
    from app import siglas

    citacoes = {n.metadata["citacao"] for n in ind.nos.values() if n.metadata["citavel"]}
    assert citacoes and all(siglas.valida(c) for c in citacoes)
    assert not any(n.metadata["citavel"] for n in ind.nos.values() if n.metadata["tipo_documento"] == "apoio")


def test_contexto_nao_entra_no_embedding(ind):
    from llama_index.core.schema import MetadataMode

    art11 = next(n for n in ind.nos.values() if n.metadata["citacao"] == "ART-11" and n.metadata["parte"] == "caput")
    embed = art11.get_content(metadata_mode=MetadataMode.EMBED)
    llm = art11.get_content(metadata_mode=MetadataMode.LLM)
    assert "Título II — Do direito ao reembolso" in embed
    assert "Este Título disciplina" not in embed and "Este Título disciplina" in llm


def test_linha_da_tabela_nao_carrega_teto(ind):
    import re

    psico = next(n for n in ind.nos.values() if n.metadata["citacao"] == "TUSS-50000462")
    assert not re.search(r"\d+(,\d+)? URS|R\$", psico.text)   # o 1,2 URS impresso está desatualizado


def test_regras_de_aplicacao_do_anexo_iv(ind):
    regras = {n.metadata["parte"]: n.metadata["aplica_a"] for n in ind.nos.values()
              if n.metadata["tipo_documento"] == "anexo_regra"}
    assert regras == {"11.1": "todos", "11.2": "3", "11.3": "todos", "11.4": "todos"}


def test_bm25_persistido_usa_o_stemmer_em_portugues(ind):
    # sem o stemmer português, o BM25 recarregado devolve tudo com nota 0, sem erro
    ind.bm25.similarity_top_k = 3
    melhor = ind.bm25.retrieve("acupuntura")[0]
    assert melhor.score > 0
    assert (melhor.node.metadata["citacao"], melhor.node.metadata["parte"]) == ("ANEXO-IV", "3.3")


def test_tabela_de_coparticipacao_volta_a_ser_tabela(ind):
    art44 = next(n for n in ind.nos.values() if n.metadata["citacao"] == "ART-44" and n.metadata["parte"] == "§ 2º")
    assert "| Plano | Até 12 meses de adesão | De 12 a 36 meses | Acima de 36 meses |" in art44.text
    assert "| Pleno | 30% | 20% | 10% |" in art44.text and "| Essencial | 35% | 25% | 15% |" in art44.text
    # a nova redação da CIRC-02 também chega ao modelo como tabela, no artigo consolidado
    art, _ = consolidar("ART-44", date(2026, 4, 25), ind, vistos=set())
    tabela = next(p for p in art.partes if p.parte == "§ 2º")
    assert tabela.fonte == "CIRC-02-2026" and "| Pleno | 40% | 30% | 20% |" in tabela.texto


def test_corte_5_primeiros_de_norma_e_apoio_depois():
    from llama_index.core.schema import NodeWithScore, TextNode

    from app.rag import cortar

    def a(nota, tipo="regulamento"):
        return NodeWithScore(node=TextNode(text="x", metadata={"tipo_documento": tipo}), score=nota)

    # norma: os 5 primeiros, qualquer nota; apoio: até 2 com nota ≥ 50% da 1ª de norma
    ordenados = [a(0.9), a(0.2), a(0.1), a(0.05), a(0.01), a(0.001), a(0.6, "apoio"), a(0.1, "apoio")]
    assert [x.score for x in cortar(ordenados)] == [0.9, 0.2, 0.1, 0.05, 0.01, 0.6]


@pytest.mark.parametrize("texto, artigos", [
    ("Sem teto automatizado — art. 78, § 1º", {"ART-78"}),
    ("observados os arts. 40 a 42", {"ART-40", "ART-41", "ART-42"}),
    ("na forma dos arts. 41 e 44 do Regulamento", {"ART-41", "ART-44"}),
    ("o teto de que trata o art. 1º desta Circular", set()),
])
def test_mencoes_a_artigos(texto, artigos):
    from app.rag import mencionados

    assert mencionados(texto) == artigos


# ------------------------------------------------------------ filtro e artigo consolidado
@pytest.mark.parametrize("sigla, dia, vale", [
    ("CIRC-04-2025", date(2025, 8, 15), True),
    ("CIRC-04-2025", date(2025, 11, 1), False),   # revogada pela CIRC-09
    ("CIRC-02-2026", date(2026, 4, 19), False),   # ainda não vigia
    ("CIRC-02-2026", date(2026, 4, 20), True),
])
def test_filtro_de_circular_por_data(ind, sigla, dia, vale):
    meta = next(n.metadata for n in ind.nos.values() if n.metadata["citacao"] == sigla)
    assert _vigente(meta, dia) is vale


def test_art41_consolidado_em_abril_de_2026(ind):
    art, completados = consolidar("ART-41", date(2026, 4, 25), ind, vistos={"ART-41", "CIRC-02-2026"})
    fontes = {p.parte: p.fonte for p in art.partes}
    assert fontes == {"caput": "CIRC-02-2026", "§ 1º": "CIRC-11-2026", "§ 2º": "CIRC-02-2026",
                      "§ 3º": "ART-41", "§ 4º": "ART-41"}
    assert "2,8 URS" in art.partes[0].texto
    assert art.fundamentos == ["ART-41", "CIRC-02-2026", "CIRC-11-2026"]
    # a busca não trouxe a CIRC-11: o § 1º foi completado pelo grafo e isso fica registrado
    assert completados == ["ART-41 § 1º <- CIRC-11-2026"]


def test_art12_volta_ao_original_depois_da_revogacao(ind):
    agosto, _ = consolidar("ART-12", date(2025, 8, 15), ind, vistos=set())
    maio, _ = consolidar("ART-12", date(2026, 5, 20), ind, vistos=set())
    assert agosto.partes[0].fonte == "CIRC-04-2025" and "150" in agosto.partes[0].texto
    assert maio.partes[0].fonte == "ART-12" and "90 (noventa)" in maio.partes[0].texto

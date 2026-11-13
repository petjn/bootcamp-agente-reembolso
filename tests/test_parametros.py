"""Os parâmetros extraídos batem com o texto, e o cálculo feito só com eles bate com os gabaritos.

Os números aqui são verificação do que está escrito na kb/, não regra do agente.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.calculo import apurar
from app.parametros import Parametros
from ingest.modelo import ancorado
from ingest.parametros import ParametroNaoEncontrado, extrair

p = Parametros.carregar()
D = Decimal


@pytest.mark.parametrize("dispositivo, parte, tipo, dia, valor, fonte", [
    ("ART-41", "caput", "teto_urs", date(2026, 1, 20), D("1.2"), "ART-41"),
    ("ART-41", "caput", "teto_urs", date(2026, 3, 10), D("1.6"), "CIRC-11-2026"),
    ("ART-41", "caput", "teto_urs", date(2026, 4, 25), D("2.8"), "CIRC-02-2026"),
    ("ART-41", "§ 2º", "teto_urs", date(2026, 4, 25), D("2.6"), "CIRC-02-2026"),
    ("ART-41", "§ 2º", "sessoes_para_continuado", date(2026, 4, 25), D("8"), "CIRC-02-2026"),  # herdado
    ("ART-73", "§ 3º", "relatorio_a_partir_da_sessao", date(2026, 1, 20), D("24"), "ART-73"),
    ("ART-73", "§ 3º", "relatorio_a_partir_da_sessao", date(2026, 3, 10), D("10"), "CIRC-11-2026"),
    ("ART-73", "§ 3º", "relatorio_a_partir_da_sessao", date(2026, 4, 25), D("5"), "CIRC-02-2026"),
    ("ART-12", "caput", "prazo_dias", date(2025, 8, 1), D("150"), "CIRC-04-2025"),
    ("ART-12", "caput", "prazo_dias", date(2025, 12, 1), D("90"), "ART-12"),
])
def test_valor_vigente(dispositivo, parte, tipo, dia, valor, fonte):
    v = p.valor(dispositivo, parte, tipo, dia)
    assert (v.valor, v.fonte) == (valor, fonte)


def test_coparticipacao_muda_na_circ02():
    antes = p.unico("coparticipacao", date(2026, 4, 19))
    depois = p.unico("coparticipacao", date(2026, 4, 20))
    assert antes.fonte == "ART-44" and antes.valor["percentuais"]["Pleno"][0] == "0.3"
    assert depois.fonte == "CIRC-02-2026" and depois.valor["percentuais"]["Pleno"][0] == "0.4"


def test_alcada_tem_dois_limites_com_escopo():
    limites = p.todos("ART-78", "§ 1º", "alcada_brl", date(2026, 5, 1))
    assert {(l.valor, l.escopo.split()[0]) for l in limites} == {(D("5000.00"), "consultas,"),
                                                                  (D("7500.00"), "os")}


def test_tabela_urs():
    assert p.valor_urs(date(2026, 4, 30)) == D("95.10")
    assert p.linha("TUSS-10101012")["artigo_teto"] == "ART-35"
    assert p.linha("TUSS-70000039")["teto_urs"] is None          # OPME: sem teto automatizado
    with pytest.raises(LookupError):
        p.valor_urs(date(2027, 1, 10))                            # não há tabela de 2027


def test_caso_01_consulta():
    a = apurar("TUSS-10101012", D("240.00"), date(2026, 4, 30), "Pleno", date(2025, 9, 1),
               reembolsado_no_ano=D("0"))
    assert a.valor_reembolso == D("144.00") and not a.parcial
    assert {"ART-35", "ART-33", "ART-43", "ART-44", "ART-47", "TUSS-10101012"} <= set(a.regras)
    assert "CIRC-02-2026" in a.regras          # D6: a coparticipação aplicada é a da CIRC-02


def test_caso_02_psicoterapia():
    a = apurar("TUSS-50000462", D("320.00"), date(2026, 4, 25), "Essencial", date(2022, 3, 1),
               reembolsado_no_ano=D("4453.53"), sessoes_anteriores=10)
    assert a.valor_reembolso == D("111.27") and a.parcial
    assert {"ART-41", "CIRC-02-2026", "ART-33", "ART-43", "ART-44", "ART-45", "ART-47",
            "TUSS-50000462"} <= set(a.regras)
    assert "CIRC-11-2026" not in a.regras


def test_texto_em_outro_estilo_sem_modelo_para_o_build():
    # se a redação muda e o padrão não reconhece, extrair() não acha nada...
    assert extrair("O valor máximo por sessão fica fixado em 2,8 unidades de referência.") == []
    # ...e a construção, sem modelo de apoio, para com erro em vez de seguir com valor velho
    from ingest import parametros
    original = parametros.extrair
    try:
        parametros.extrair = lambda t: [] if "2,8" in t else original(t)
        with pytest.raises(ParametroNaoEncontrado):
            parametros.construir(extrator_modelo=None)
    finally:
        parametros.extrair = original


class _ModeloFalso:
    """Simula o Gemma devolvendo uma resposta fixa, para testar as travas sem chamar o modelo."""
    def __init__(self, valor):
        self.valor = valor

    def with_structured_output(self, schema):
        modelo = self

        class _R:
            def invoke(self, _):
                return schema(encontrado=True, valor=modelo.valor)
        return _R()


@pytest.mark.parametrize("texto, resposta, aceita", [
    ("teto fixado em 2,8 unidades de referência", "2,8", True),
    ("teto fixado em 2,8 unidades de referência", "2,6", False),                 # inventou
    ("o teto passa a corresponder a duas URS e meia", "duas URS e meia", False),  # não é número
])
def test_travas_do_fallback(texto, resposta, aceita):
    from ingest.modelo import extrair_com_modelo
    r = extrair_com_modelo(texto, "teto_urs", llm=_ModeloFalso(resposta))
    assert (r is not None) == aceita


def test_ancoragem():
    assert ancorado("2,8", "teto fixado em 2,8 unidades")
    assert not ancorado("2,6", "teto fixado em 2,8 unidades")
    assert not ancorado("8", "teto de 2,8 URS")               # não aceita pedaço de outro número

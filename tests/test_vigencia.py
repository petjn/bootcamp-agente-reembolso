"""Trava as cadeias de vigência conhecidas da base.

    .venv\\Scripts\\python.exe -m pytest tests -q

Cada caso diz: dispositivo, parte, data do atendimento -> fonte da redação vigente.
"""

from datetime import date

import pytest

from app.vigencia import Grafo

g = Grafo.carregar()


@pytest.mark.parametrize("dia, fonte", [
    # art. 12 (prazo): CIRC-04 altera; CIRC-09 revoga a 04 e volta o original (art. 5º, § 1º)
    (date(2025, 6, 30), "ART-12"),        # antes da CIRC-04
    (date(2025, 7, 1), "CIRC-04-2025"),   # primeiro dia da CIRC-04
    (date(2025, 10, 31), "CIRC-04-2025"),
    (date(2025, 11, 1), "ART-12"),        # CIRC-09 revogou a 04: redação original
    (date(2026, 5, 20), "ART-12"),
])
def test_art12_revogacao_restaura_original(dia, fonte):
    assert g.redacao("ART-12", "caput", dia).fonte == fonte


@pytest.mark.parametrize("dia, fonte", [
    # art. 41 (teto psicoterapia): CIRC-11 (01/02) e depois CIRC-02 (20/04).
    # A de número menor vale depois, porque a precedência é pela vigência (art. 5º, § 4º).
    (date(2026, 1, 31), "ART-41"),
    (date(2026, 2, 1), "CIRC-11-2026"),
    (date(2026, 3, 10), "CIRC-11-2026"),
    (date(2026, 4, 19), "CIRC-11-2026"),
    (date(2026, 4, 20), "CIRC-02-2026"),
    (date(2026, 5, 20), "CIRC-02-2026"),
])
def test_art41_caput_precedencia_por_vigencia(dia, fonte):
    assert g.redacao("ART-41", "caput", dia).fonte == fonte


def test_eficacia_futura_da_circ11_anulada_pela_circ02():
    # CIRC-11 (vigência 01/02/2026) agendou 1,8 URS para 2027; a CIRC-02 (vigência
    # 20/04/2026) alterou o mesmo caput depois e prevalece: em 2027 segue a CIRC-02.
    r = g.redacao("ART-41", "caput", date(2027, 2, 10))
    assert r.fonte == "CIRC-02-2026"
    assert "2,8 URS" in r.texto


def test_art41_textos_vigentes():
    assert "1,2 URS" not in g.redacao("ART-41", "caput", date(2026, 3, 10)).texto
    assert "1,6 URS" in g.redacao("ART-41", "caput", date(2026, 3, 10)).texto
    assert "2,8 URS" in g.redacao("ART-41", "caput", date(2026, 5, 20)).texto
    assert "2,6 URS" in g.redacao("ART-41", "§ 2º", date(2026, 5, 20)).texto
    assert "1,4 URS" in g.redacao("ART-41", "§ 2º", date(2026, 3, 10)).texto


def test_paragrafo_nao_alterado_pela_circular_mais_recente_continua_da_anterior():
    # CIRC-02 não menciona o § 1º do art. 41 (art. 5º, § 2º): segue a redação da CIRC-11
    assert g.redacao("ART-41", "§ 1º", date(2026, 5, 20)).fonte == "CIRC-11-2026"


def test_fundamentos_do_caso_02_de_treino():
    # gabarito do caso 02 (conversa em 2026-05-20) cita ART-41 e CIRC-02-2026, não a CIRC-11
    assert g.fundamentos("ART-41", date(2026, 5, 20), partes=["caput"]) == ["ART-41", "CIRC-02-2026"]
    assert g.fundamentos("ART-41", date(2026, 5, 20), partes=["§ 2º"]) == ["ART-41", "CIRC-02-2026"]


def test_artigo_sem_circular_cita_so_ele():
    assert g.fundamentos("ART-35", date(2026, 5, 20)) == ["ART-35"]


def test_tuss_psicoterapia_sobreposto_pelo_art41():
    assert g.teto_sobre_tuss("TUSS-50000462", date(2026, 1, 15)) is None   # vale a tabela
    assert g.teto_sobre_tuss("TUSS-50000462", date(2026, 3, 10)).fonte == "CIRC-11-2026"
    assert g.teto_sobre_tuss("TUSS-50000462", date(2026, 5, 20)).fonte == "CIRC-02-2026"
    assert g.teto_sobre_tuss("TUSS-10101012", date(2026, 5, 20)) is None


def test_art44_coparticipacao_e_art73_relatorio():
    assert g.redacao("ART-44", "§ 2º", date(2026, 4, 19)).fonte == "ART-44"
    assert g.redacao("ART-44", "§ 2º", date(2026, 4, 20)).fonte == "CIRC-02-2026"
    assert g.redacao("ART-73", "§ 3º", date(2026, 3, 10)).fonte == "CIRC-11-2026"
    assert g.redacao("ART-73", "§ 3º", date(2026, 5, 20)).fonte == "CIRC-02-2026"

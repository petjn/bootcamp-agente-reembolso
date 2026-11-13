"""A decisão (código) reproduz o gabarito dos casos de treino 04 a 16, a partir do molde que o
documento deveria produzir (conferido à mão contra cada PDF) e do cadastro e histórico de cada persona.

O julgamento do Anexo IV é do modelo e tem teste próprio; aqui ele entra pronto: "não excluído" em todos,
menos na acupuntura sem indicação clínica (caso 08), que é procedimento de fronteira.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from app.decisao import JulgamentoExclusao, decidir
from app.parametros import Parametros

CASOS = Path(__file__).resolve().parents[1] / "casos" / "treino"

# caso: (categoria, data do atendimento, TUSS, valor pago, complementares)
DOCUMENTOS = {
    "04": ("SESSAO_TERAPIA", "2026-03-10", "TUSS-50000462", 200.0, []),
    "05": ("CONSULTA_MEDICA", "2026-05-04", "TUSS-10101055", 300.0, []),
    "07": ("EXAME_DIAGNOSTICO", "2026-05-10", "TUSS-40301258", 90.0, []),
    "08": ("SESSAO_TERAPIA", "2026-05-11", "TUSS-50000646", 150.0, []),
    "09": ("SESSAO_TERAPIA", "2026-05-13", "TUSS-50000550", 5200.0, []),
    "10": ("SESSAO_TERAPIA", "2026-05-12", "TUSS-50000462", 400.0,
           [{"molde": {"classificacao": "RELATORIO_CLINICO", "indica_manutencao_tratamento": True}}]),
    "11": ("SESSAO_TERAPIA", "2026-05-08", "TUSS-50000462", 260.0, []),
    "12": ("CONSULTA_MEDICA", "2026-05-07", "TUSS-10101087", 420.0, []),
    "13": ("CONSULTA_MEDICA", "2026-05-11", "TUSS-10101047", 350.0, []),
    "15": ("RELATORIO_CLINICO", "2026-05-13", "TUSS-10104011", 150.0, []),
    "16": ("EXAME_DIAGNOSTICO", "2026-05-18", "TUSS-40301082", 180.0, []),
}
FRONTEIRA = {"08": JulgamentoExclusao(item="3.3", desfecho="falta_indicacao")}


def _molde(categoria, data, tuss, valor):
    linha = Parametros.carregar().linhas[tuss]
    return {"classificacao": categoria, "c4_data_atendimento": data, "c6_valor_total": valor,
            "c5_itens": [{"codigo_tuss": tuss, "descricao": linha["descricao"], "quantidade": 1, "valor": valor,
                          "na_tabela": True, "categoria_tabela": linha["categoria_tabela"]}],
            "campos_faltando": [], "pendencias": [], "urgencia_declarada": False, "c10_indicacao_clinica": False}


@pytest.mark.parametrize("caso", sorted(DOCUMENTOS))
def test_decisao_do_caso(caso):
    pasta = next(CASOS.glob(f"{caso}_*"))
    persona = json.loads((pasta / "persona.json").read_text(encoding="utf-8"))
    esperado = json.loads((pasta / "esperado.json").read_text(encoding="utf-8"))
    categoria, data, tuss, valor, complementares = DOCUMENTOS[caso]
    historico = [{"data": h["data_atendimento"], "categoria": h["categoria"],
                  "valor_reembolsado": str(h["valor_reembolsado_brl"])} for h in persona.get("historico", [])]
    beneficiario = {"plano": persona["plano"], "data_adesao": persona["data_adesao"], "status": persona["status"]}
    julgamento = FRONTEIRA.get(caso)
    d = decidir(_molde(categoria, data, tuss, valor), complementares, beneficiario, historico,
                date.fromisoformat(esperado["_data_da_conversa"]), julgar=(lambda m, dia: julgamento))
    assert d.decisao == esperado["decisao"], d.motivo
    if esperado["decisao"] in ("APROVADO", "APROVADO_PARCIAL"):
        assert d.valor_reembolso == pytest.approx(esperado["valor_reembolso_brl"], abs=0.01)
    assert set(esperado["regras_aplicadas"]) <= set(d.regras), set(esperado["regras_aplicadas"]) - set(d.regras)

"""Regras da auditoria norma × código de 2026-10-21 (D93), sem modelo: o molde é o que o leitor devolveria."""

from datetime import date
from decimal import Decimal

from app.calculo import apurar
from app.decisao import FORA_DA_TABELA, decidir
from app.parametros import Parametros

HOJE = date(2026, 5, 20)
B = {"plano": "Essencial", "data_adesao": "2021-09-01", "status": "ATIVO"}
L = Parametros.carregar().linhas


def item(codigo, valor, data=None, descricao=None):
    return {"codigo_tuss": codigo, "descricao": descricao or L.get(codigo or "", {}).get("descricao", ""),
            "quantidade": 1, "valor": valor, "data": data, "na_tabela": codigo in L,
            "categoria_tabela": L.get(codigo or "", {}).get("categoria_tabela")}


def molde(categoria, data, itens, **extra):
    return {"classificacao": categoria, "c4_data_atendimento": data, "c6_valor_total": sum(i["valor"] for i in itens),
            "c5_itens": itens, "campos_faltando": [], "pendencias": [], "urgencia_declarada": False,
            "c10_indicacao_clinica": False, **extra}


def test_telessaude_tem_o_teto_da_consulta():
    # art. 35, § 2º; art. 70; NT-02, Caso 22: 5 URS, e não os 3,4 da linha da Tabela
    r = apurar("TUSS-10102098", Decimal("450"), date(2026, 5, 7), "Pleno", date(2023, 3, 1), Decimal(0))
    assert r.valor_reembolso == Decimal("360.00") and "ART-70" in r.regras


def test_segunda_consulta_com_o_mesmo_profissional_em_15_dias_sai():
    m = molde("CONSULTA_MEDICA", "2026-05-12", [item("TUSS-10101039", 400.0, "2026-05-05"),
                                                item("TUSS-10101039", 400.0, "2026-05-12")])
    d = decidir(m, [], B, [], HOJE, julgar=None)
    assert (d.decisao, d.valor_reembolso) == ("APROVADO", 300.0) and "ART-36" in d.regras
    # com justificativa clínica no documento, as duas valem (art. 36, § 1º)
    d = decidir({**m, "c10_indicacao_clinica": True}, [], B, [], HOJE, julgar=None)
    assert d.valor_reembolso == 600.0
    # consulta e retorno da mesma especialidade contam juntos; especialidades distintas, não (§ 2º)
    retorno = molde("CONSULTA_MEDICA", "2026-05-15", [item("TUSS-10101047", 300.0, "2026-05-05"),
                                                      item("TUSS-10102018", 150.0, "2026-05-15")])
    assert decidir(retorno, [], B, [], HOJE, julgar=None).valor_reembolso == 225.0
    distintas = molde("CONSULTA_MEDICA", "2026-05-12", [item("TUSS-10101039", 400.0, "2026-05-05"),
                                                        item("TUSS-10101063", 300.0, "2026-05-12")])
    assert decidir(distintas, [], B, [], HOJE, julgar=None).valor_reembolso == 525.0


def test_procedimento_descrito_fora_da_tabela_e_negado_e_o_generico_fica_pendente():
    m = molde("CONSULTA_MEDICA", "2026-05-12", [item(None, 300.0, descricao="Sessão de constelação familiar")])
    d = decidir(m, [], B, [], HOJE, julgar=None, classificar=lambda i, dia: [FORA_DA_TABELA])
    assert d.decisao == "NEGADO" and d.regras[0] == "ART-56"
    d = decidir(m, [], B, [], HOJE, julgar=None, classificar=lambda i, dia: [])
    assert d.decisao == "PENDENTE_DOCUMENTO" and d.pendencias == ["P12"]
    # código que não está na Tabela: reclassifica pela descrição; sem achar, P14
    m = molde("CONSULTA_MEDICA", "2026-05-12", [item("TUSS-99999999", 300.0, descricao="Consulta")])
    d = decidir(m, [], B, [], HOJE, julgar=None, classificar=lambda i, dia: [])
    assert d.pendencias == ["P14"]


def test_linha_da_tabela_so_vale_para_quem_tem_o_registro_dela():
    m = molde("CONSULTA_MEDICA", "2026-05-08", [item(None, 180.0, descricao="Sessão de quiropraxia - coluna")],
              c3_registro_conselho="ABQ 1.204")
    d = decidir(m, [], B, [], HOJE, julgar=None, classificar=lambda i, dia: ["TUSS-50000916"])
    assert d.decisao == "NEGADO" and d.regras[0] == "ART-56"
    d = decidir({**m, "c3_registro_conselho": "CREFITO-3 214.508-F"}, [], B, [], HOJE, julgar=None,
                classificar=lambda i, dia: ["TUSS-50000916"])
    assert d.decisao == "APROVADO"


def test_moeda_estrangeira_vai_a_analista():
    m = molde("CONSULTA_MEDICA", "2026-05-12", [item("TUSS-10101063", 80.0)], moeda_estrangeira=True)
    d = decidir(m, [], B, [], HOJE, julgar=None)
    assert d.decisao == "ESCALADO_ANALISTA" and "ART-69" in d.regras
    # sem código e com registro de conselho estrangeiro: não sai pela Tabela, vai a analista (D98)
    m = molde("CONSULTA_MEDICA", "2026-05-12", [item(None, 80.0, descricao="Consulta de medicina geral")],
              moeda_estrangeira=True, c3_registro_conselho="Colegio Medico 4.512")
    d = decidir(m, [], B, [], HOJE, julgar=None, classificar=lambda i, dia: ["TUSS-10101012"])
    assert d.decisao == "ESCALADO_ANALISTA" and "ART-69" in d.regras


def test_emissao_antes_do_atendimento():
    from app.agents.documento import emitido_antes

    assert emitido_antes("Data de emissão: 02/05/2026", "08/05/2026", [])
    assert not emitido_antes("Data de emissão: 08/05/2026", "08/05/2026", [])
    assert not emitido_antes("Recibo sem data de emissão", "08/05/2026", [])

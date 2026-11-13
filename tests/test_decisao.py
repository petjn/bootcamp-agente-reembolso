"""A decisão (M5) reproduz os gabaritos dos 3 casos a partir do documento já lido.

Sem modelo: o molde é o que o ag_documento devolveria, e o julgamento do Anexo IV
é desligado (nenhum dos 3 casos é exclusão). "Hoje" é 20/05/2026, o dia das conversas.
"""

from datetime import date

from app.decisao import decidir

HOJE = date(2026, 5, 20)


def molde(categoria, data, itens, total, faltando=()):
    return {"classificacao": categoria, "c4_data_atendimento": data, "c6_valor_total": total, "c5_itens": [
        {"codigo_tuss": c, "descricao": d, "quantidade": 1, "valor": v} for c, d, v in itens],
        "campos_faltando": list(faltando), "pendencias": [], "urgencia_declarada": False,
        "c10_indicacao_clinica": False}


def test_caso_01_consulta_aprovada():
    m = molde("CONSULTA_MEDICA", "2026-04-30", [("TUSS-10101012", "Consulta médica em consultório", 240.0)], 240.0)
    b = {"plano": "Pleno", "data_adesao": "2025-09-01", "status": "ATIVO"}
    d = decidir(m, [], b, [], HOJE, julgar=None)
    assert (d.decisao, d.valor_reembolso) == ("APROVADO", 144.0)
    assert {"ART-35", "ART-33", "ART-43", "ART-44", "ART-47", "TUSS-10101012"} <= set(d.regras)


HISTORICO_02 = [{"data": f"2026-{m:02d}-{dia:02d}", "categoria": "SESSAO_TERAPIA", "valor_reembolsado": v}
                for (m, dia), v in zip([(1, 12), (1, 19), (1, 26), (2, 2), (2, 9), (2, 23), (3, 2), (3, 16),
                                        (3, 30), (4, 13)],
                                       ["445.38"] * 9 + [str(round(4453.53 - 445.38 * 9, 2))])]
B02 = {"plano": "Essencial", "data_adesao": "2022-03-01", "status": "ATIVO"}
M02 = molde("SESSAO_TERAPIA", "2026-04-25", [("TUSS-50000462", "Sessão de psicoterapia individual", 320.0)], 320.0)


def test_caso_02_sem_relatorio_fica_pendente():
    d = decidir(M02, [], B02, HISTORICO_02, HOJE, julgar=None)
    assert d.decisao == "PENDENTE_DOCUMENTO" and d.valor_reembolso is None
    assert d.pendencias and "ART-73" in d.regras


def test_caso_02_com_relatorio_aprovado_parcial():
    relatorio = {"molde": {"classificacao": "RELATORIO_CLINICO", "indica_manutencao_tratamento": True}}
    d = decidir(M02, [relatorio], B02, HISTORICO_02, HOJE, julgar=None)
    assert (d.decisao, d.valor_reembolso) == ("APROVADO_PARCIAL", 111.27)
    assert {"ART-41", "CIRC-02-2026", "ART-73", "ART-33", "ART-43", "ART-44", "ART-45", "ART-47",
            "TUSS-50000462"} <= set(d.regras)


def test_caso_03_protese_escala():
    m = molde("MATERIAL_OPME", "2026-04-30", [("TUSS-70000039", "Prótese total de joelho", 7400.0),
                                              (None, "Artroplastia total de joelho", 1800.0)], 9200.0)
    b = {"plano": "Pleno", "data_adesao": "2024-09-01", "status": "ATIVO"}
    d = decidir(m, [], b, [], HOJE, julgar=None)
    assert d.decisao == "ESCALADO_ANALISTA" and d.escalar and d.valor_reembolso is None
    assert d.regras[0] == "ART-78" and set(d.regras) <= {"ART-78", "TUSS-70000039"}


def test_prazo_vencido_com_a_data_real():
    m = molde("CONSULTA_MEDICA", "2026-04-30", [("TUSS-10101012", "Consulta", 240.0)], 240.0)
    b = {"plano": "Pleno", "data_adesao": "2025-09-01", "status": "ATIVO"}
    assert decidir(m, [], b, [], date(2026, 10, 8), julgar=None).decisao == "NEGADO"


def test_exclusao_do_anexo_iv_e_negado_com_categoria_despesa_nao_coberta():
    from app.decisao import JulgamentoExclusao

    m = molde("CONSULTA_MEDICA", "2026-04-30", [(None, "Procedimento estético", 500.0)], 500.0)
    b = {"plano": "Pleno", "data_adesao": "2024-09-01", "status": "ATIVO"}
    d = decidir(m, [], b, [], HOJE, julgar=lambda m, dia: JulgamentoExclusao(item="1.1", desfecho="excluido"))
    assert (d.decisao, d.categoria) == ("NEGADO", "DESPESA_NAO_COBERTA") and {"ANEXO-IV", "ART-51"} <= set(d.regras)


def test_sem_item_para_calcular_vai_ao_analista_e_nao_e_limite_esgotado():
    m = molde("CONSULTA_MEDICA", "2026-04-30", [("TUSS-10101012", "Consulta", None)], 240.0)
    b = {"plano": "Pleno", "data_adesao": "2025-09-01", "status": "ATIVO"}
    d = decidir(m, [], b, [], HOJE, julgar=None)
    assert d.decisao == "ESCALADO_ANALISTA" and "limite" not in d.motivo


def test_exame_de_alta_complexidade_sem_pedido_medico_fica_pendente():
    m = molde("EXAME_DIAGNOSTICO", "2026-05-05", [("TUSS-40901017", "Ressonância magnética de crânio", 900.0)], 900.0)
    b = {"plano": "Pleno", "data_adesao": "2024-03-01", "status": "ATIVO"}
    d = decidir(m, [], b, [], HOJE, julgar=None)
    assert (d.decisao, d.valor_reembolso, d.pendencias) == ("PENDENTE_DOCUMENTO", None, ["P23"])
    assert "ART-38" in d.regras
    pedido = {"molde": {"classificacao": "PEDIDO_MEDICO", "c2_prestador_nome": "Dra. A", "c3_registro_conselho": "CRM-SP 1",
                        "c4_data_atendimento": "2026-04-20"}}
    assert (decidir(m, [pedido], b, [], HOJE, julgar=None).valor_reembolso) == 630.0
    sem_solicitante = {"molde": {**pedido["molde"], "c3_registro_conselho": None}}
    assert decidir(m, [sem_solicitante], b, [], HOJE, julgar=None).pendencias == ["P24"]
    vencido = {"molde": {**pedido["molde"], "c4_data_atendimento": "2026-01-20"}}   # 105 dias antes do exame
    assert decidir(m, [vencido], b, [], HOJE, julgar=None).pendencias == ["P23"]
    # sem a data da solicitação (NT-02, 9.1, IV) o pedido não serve: não há como saber se vale (D92)
    sem_data = {"molde": {**pedido["molde"], "c4_data_atendimento": None}}
    d = decidir(m, [sem_data], b, [], HOJE, julgar=None)
    assert d.pendencias == ["P23"] and "data da solicitação" in d.falta_cliente[0]


def test_item_excluido_discriminado_sai_da_base_e_o_resto_e_apurado():
    from app.decisao import JulgamentoExclusao

    def julgar(m, dia):
        taxa = m["c5_itens"][0]["descricao"].startswith("Taxa")
        return JulgamentoExclusao(item="5.2" if taxa else None, motivo="", desfecho="excluido" if taxa else "coberto")

    m = molde("CONSULTA_MEDICA", "2026-05-08", [("TUSS-10101095", "Consulta em ginecologia", 380.0),
                                                (None, "Taxa de agendamento", 30.0)], 410.0)
    b = {"plano": "Pleno", "data_adesao": "2025-11-03", "status": "ATIVO"}
    d = decidir(m, [], b, [], HOJE, julgar=julgar)
    assert (d.decisao, d.valor_reembolso) == ("APROVADO", 228.0)
    assert {"ART-59", "ANEXO-IV"} <= set(d.regras) and "Taxa de agendamento" in d.memoria[0]


def test_ficha_do_pedido_mostra_cada_requisito_conferido():
    m = molde("EXAME_DIAGNOSTICO", "2026-05-05", [("TUSS-40901017", "Ressonância magnética de crânio", 900.0)], 900.0)
    b = {"plano": "Pleno", "data_adesao": "2024-03-01", "status": "ATIVO"}
    ficha = {r["regra"]: r["situacao"] for r in decidir(m, [], b, [], HOJE, julgar=None).ficha}
    assert ficha["art. 23"] == "cumprido" and ficha["art. 12"] == "cumprido" and ficha["art. 38"] == "falta"
    assert "art. 45" not in ficha   # pendente: o valor não é apurado, e a ficha não diz o que não conferiu
    carencia = decidir(m, [], {**b, "data_adesao": "2026-04-01"}, [], HOJE, julgar=None).ficha
    assert carencia[-1]["regra"] == "art. 23" and carencia[-1]["situacao"] == "impede"


# ------------------------------------------------------------------ ramos da árvore (D79)
def _item(codigo, valor, data=None, quantidade=1, descricao=None):
    from app.parametros import Parametros

    linha = Parametros.carregar().linhas.get(codigo or "", {})
    return {"codigo_tuss": codigo, "descricao": descricao or linha.get("descricao", "procedimento"), "quantidade": quantidade,
            "valor": valor, "data": data, "na_tabela": bool(linha), "categoria_tabela": linha.get("categoria_tabela")}


def _doc(categoria, data, itens):
    return {"classificacao": categoria, "c4_data_atendimento": data, "c6_valor_total": sum(i["valor"] or 0 for i in itens),
            "c5_itens": itens, "campos_faltando": [], "pendencias": [], "urgencia_declarada": False,
            "c10_indicacao_clinica": False}


ANTIGO = {"plano": "Pleno", "data_adesao": "2022-01-01", "status": "ATIVO"}


def test_varias_sessoes_discriminadas_sao_apuradas_sessao_a_sessao():
    m = _doc("SESSAO_TERAPIA", "2026-05-11", [_item("TUSS-50000558", 150.0, "2026-05-04"),
                                              _item("TUSS-50000558", 150.0, "2026-05-11")])
    d = decidir(m, [], ANTIGO, [], HOJE, julgar=None, classificar=None)
    assert (d.decisao, d.valor_reembolso) == ("APROVADO", 228.24)   # 2 × (teto R$ 142,65 − 20%)
    ficha = {r["regra"]: r["detalhe"] for r in d.ficha}
    assert "1ª a 2ª" in ficha["art. 40"] and "9 dias" in ficha["art. 12"]   # o prazo conta da última sessão


def test_sessao_antes_da_carencia_sai_e_a_outra_segue():
    m = _doc("SESSAO_TERAPIA", "2026-05-11", [_item("TUSS-50000558", 150.0, "2026-05-04"),
                                              _item("TUSS-50000558", 150.0, "2026-05-11")])
    d = decidir(m, [], {**ANTIGO, "data_adesao": "2025-12-10"}, [], HOJE, julgar=None, classificar=None)
    assert (d.decisao, d.valor_reembolso) == ("APROVADO", 85.59)
    assert "ART-24" in d.regras and any("antes da carência" in x for x in d.memoria)


def test_varias_sessoes_num_valor_so_ficam_pendentes():
    m = _doc("SESSAO_TERAPIA", "2026-05-11", [_item("TUSS-50000558", 1500.0, quantidade=10)])
    d = decidir(m, [], ANTIGO, [], HOJE, julgar=None, classificar=None)
    # as 10 sessões contam para o relatório (a partir da 5ª, CIRC-02-2026): todas as pendências de uma vez (art. 18, § 1º)
    assert (d.decisao, d.pendencias) == ("PENDENTE_DOCUMENTO", ["P16", "P20"])
    assert any(r["regra"] == "art. 19" and "60 dias" in r["detalhe"] for r in d.ficha)


def test_item_sem_codigo_e_classificado_pela_descricao_com_o_menor_teto():
    m = _doc("EXAME_DIAGNOSTICO", "2026-05-11", [_item(None, 150.0, descricao="ultrassom do abdome")])
    d = decidir(m, [], ANTIGO, [], HOJE, julgar=None, classificar=lambda i, dia: ["TUSS-40808025", "TUSS-40808017"])
    assert (d.decisao, d.valor_reembolso) == ("APROVADO", 120.0)
    assert {"ART-34", "TUSS-40808017"} <= set(d.regras)


def test_item_sem_codigo_que_nao_se_classifica_fica_pendente():
    m = _doc("CONSULTA_MEDICA", "2026-05-11", [_item(None, 150.0, descricao="serviços prestados")])
    d = decidir(m, [], ANTIGO, [], HOJE, julgar=None, classificar=lambda i, dia: [])
    assert (d.decisao, d.pendencias) == ("PENDENTE_DOCUMENTO", ["P12"])


def test_cirurgia_vai_ao_analista():
    m = _doc("CONSULTA_MEDICA", "2026-05-11", [_item("TUSS-30101018", 3000.0)])
    d = decidir(m, [], ANTIGO, [], HOJE, julgar=None, classificar=None)
    assert (d.decisao, d.escalar) == ("ESCALADO_ANALISTA", True) and "ART-83" in d.regras


def test_relatorio_com_indicacao_clinica_contemporaneo_libera_o_procedimento_de_fronteira():
    from app.decisao import JulgamentoExclusao

    def julgar(m, dia):
        return JulgamentoExclusao(item="3.3", desfecho="coberto" if m["c10_indicacao_clinica"] else "falta_indicacao")

    m = _doc("SESSAO_TERAPIA", "2026-05-11", [_item("TUSS-50000646", 100.0)])
    relatorio = lambda data: {"molde": {"classificacao": "RELATORIO_CLINICO", "c10_indicacao_clinica": True,  # noqa: E731
                                        "c4_data_atendimento": data}}
    d = decidir(m, [relatorio("2026-05-10")], ANTIGO, [], HOJE, julgar=julgar, classificar=None)
    assert (d.decisao, d.valor_reembolso) == ("APROVADO", 80.0)
    depois = decidir(m, [relatorio("2026-05-15")], ANTIGO, [], HOJE, julgar=julgar, classificar=None)
    assert (depois.decisao, depois.pendencias) == ("PENDENTE_DOCUMENTO", ["P25"])   # emitido depois: não o alcança


def test_relatorio_sem_indicacao_de_manutencao_e_p21():
    relatorio = {"molde": {"classificacao": "RELATORIO_CLINICO", "indica_manutencao_tratamento": False}}
    d = decidir(M02, [relatorio], B02, HISTORICO_02, HOJE, julgar=None, classificar=None)
    assert (d.decisao, d.pendencias) == ("PENDENTE_DOCUMENTO", ["P21"])


def test_relatorio_sem_assinatura_e_p22():
    relatorio = {"molde": {"classificacao": "RELATORIO_CLINICO", "indica_manutencao_tratamento": True,
                           "c7_assinatura": False}}
    d = decidir(M02, [relatorio], B02, HISTORICO_02, HOJE, julgar=None, classificar=None)
    assert (d.decisao, d.pendencias) == ("PENDENTE_DOCUMENTO", ["P22"])


def test_atendimento_e_despesa_excluida_num_valor_so_ficam_pendentes():
    from app.decisao import JulgamentoExclusao

    m = _doc("CONSULTA_MEDICA", "2026-05-11", [_item("TUSS-10101012", 300.0)])
    julgar = lambda m, dia: JulgamentoExclusao(item="5.1", desfecho="excluido")  # noqa: E731
    d = decidir(m, [], ANTIGO, [], HOJE, julgar=julgar, classificar=None)
    assert (d.decisao, d.pendencias) == ("PENDENTE_DOCUMENTO", ["P16"]) and "ART-59" in d.regras
    so_taxa = _doc("CONSULTA_MEDICA", "2026-05-11", [_item(None, 30.0, descricao="taxa administrativa")])
    assert decidir(so_taxa, [], ANTIGO, [], HOJE, julgar=julgar, classificar=None).decisao == "NEGADO"


def test_segundo_relatorio_sozinho_no_ano_e_negado():
    m = _doc("RELATORIO_CLINICO", "2026-05-13", [_item("TUSS-10104011", 150.0)])
    historico = [{"data": "2026-02-01", "categoria": "RELATORIO_CLINICO", "valor_reembolsado": "76.08"}]
    assert decidir(m, [], ANTIGO, [], HOJE, julgar=None, classificar=None).decisao == "APROVADO"
    assert decidir(m, [], ANTIGO, historico, HOJE, julgar=None, classificar=None).decisao == "NEGADO"


def test_procedimento_lido_como_material_e_excluido_pelo_anexo_iv_e_negado():
    from app.decisao import JulgamentoExclusao

    m = _doc("MATERIAL_OPME", "2026-05-05", [_item(None, 800.0, descricao="Sessão de criolipólise")])
    d = decidir(m, [], ANTIGO, [], HOJE, julgar=lambda m, dia: JulgamentoExclusao(item="1.19", desfecho="excluido"),
                classificar=None)
    assert d.decisao == "NEGADO"   # o Anexo IV vem antes do OPME (D82)
    avulso = decidir(m, [], ANTIGO, [], HOJE, classificar=None,
                     julgar=lambda m, dia: JulgamentoExclusao(item="4.11", desfecho="excluido"))
    assert avulso.decisao == "ESCALADO_ANALISTA"   # material avulso vai a analista (D78)

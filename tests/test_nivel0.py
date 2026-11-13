"""Nível 0 do mapa de blocos (docs/mapa_blocos_testes.md): funções de código, sem modelo e sem rede.
Cada situação tem um gabarito."""

from datetime import date
from decimal import Decimal

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents import documento, responder
from app.agents.estado import complementares, desta_mensagem, documento_ativo
from app.agents.reescrita import Carteirinha, acertar_carteirinhas, nova_rodada
from app.agents.supervisor import _encerrar, antes_de_responder, falta_triagem
from app.agents.triagem import carteirinhas
from app.calculo import apurar, meses_completos


# ------------------------------------------------------------------ cálculo
@pytest.mark.parametrize("args, valor, parcial, limitou_teto", [
    # consulta abaixo do teto: só a coparticipação
    (("TUSS-10101012", "240", date(2026, 4, 30), "Pleno", date(2025, 9, 1), "0"), "144.00", False, False),
    # sessão acima do teto, na redação anterior à circular de abril: o teto corta, mas não é parcial
    (("TUSS-50000462", "200", date(2026, 3, 10), "Pleno", date(2024, 1, 15), "250"), "121.73", False, True),
    # saldo anual menor que o apurado: parcial (art. 45, § 2º)
    (("TUSS-10104011", "150", date(2026, 5, 13), "Pleno", date(2019, 4, 1), "4520"), "44.80", True, True),
    # saldo esgotado: zero
    (("TUSS-40301082", "180", date(2026, 5, 18), "Pleno", date(2017, 6, 1), "4564.80"), "0.00", True, True),
])
def test_apuracao(args, valor, parcial, limitou_teto):
    tuss, pago, dia, plano, adesao, reembolsado = args
    a = apurar(tuss, Decimal(pago), dia, plano, adesao, Decimal(reembolsado))
    assert a.valor_reembolso == Decimal(valor) and a.parcial == parcial
    assert ("o teto limitou" in a.memoria[1]) == limitou_teto
    assert "ART-45" in a.regras   # o saldo anual é sempre apurado


def test_sessao_do_acompanhamento_continuado_usa_o_teto_do_paragrafo():
    a = apurar("TUSS-50000462", Decimal("400"), date(2026, 5, 12), "Essencial", date(2019, 3, 1),
               Decimal("4374.80"), sessoes_anteriores=29)
    assert a.valor_reembolso == Decimal("185.45")
    # a memória diz qual parte do artigo deu o teto e por quê
    assert a.memoria[0].startswith("teto do acompanhamento continuado (art. 41, § 2º: já havia 29 sessões")
    caput = apurar("TUSS-50000462", Decimal("200"), date(2026, 3, 10), "Pleno", date(2024, 1, 15), Decimal("250"))
    assert caput.memoria[0].startswith("teto do procedimento (art. 41, caput): 1.6 URS")
    assert "= R$ 152.16 " in caput.memoria[0]   # valores da memória com duas casas


@pytest.mark.parametrize("inicio, fim, meses", [
    (date(2024, 1, 15), date(2024, 2, 15), 1), (date(2024, 1, 15), date(2024, 2, 14), 0),
    (date(2024, 1, 31), date(2024, 2, 29), 0), (date(2025, 9, 1), date(2026, 4, 30), 7),
])
def test_meses_completos(inicio, fim, meses):
    assert meses_completos(inicio, fim) == meses


# ------------------------------------------------------------------ conferência do documento
TEXTO = """Recebi de: Ana Souza Lima
CPF do paciente: 123.456.789-09
A importância de: R$ 250,00
Referente a: Consulta médica
Código TUSS: 10101012
Data do atendimento: 02/03/2026
Profissional: Dr. Caio Prado  CPF/CNPJ: 12.345.678/0001-90  Registro: CRM-SP 10.000
______________________________
Dr. Caio Prado"""


def _molde(**extra):
    base = dict(documento_fiscal=True, c1_beneficiario_nome="Ana Souza Lima", c1_beneficiario_cpf="123.456.789-09",
                c2_prestador_nome="Dr. Caio Prado", c2_prestador_cpf_cnpj="12.345.678/0001-90",
                c3_registro_conselho="CRM-SP 10.000", c4_data_atendimento="02/03/2026",
                c5_itens=[documento.Item(descricao="Consulta médica", codigo_tuss="10101012", valor="250,00")],
                c6_valor_total="250,00", c7_assinatura=True, c8_numero_sessao=None, c9_pedido_medico=False,
                c10_indicacao_clinica=False)
    return documento.MoldeValido(**{**base, **extra})


def test_molde_completo_nao_tem_campo_faltando():
    m = documento.conferir("anexo_01", "CONSULTA_MEDICA", _molde(), TEXTO)
    assert m["campos_faltando"] == [] and m["c6_valor_total"] == 250.0 and m["c4_data_atendimento"] == "2026-03-02"
    assert m["c5_itens"][0]["codigo_tuss"] == "TUSS-10101012" and m["c5_itens"][0]["na_tabela"]


def test_valor_e_codigo_que_nao_estao_no_texto_saem_do_molde():
    m = documento.conferir("anexo_01", "CONSULTA_MEDICA", _molde(
        c6_valor_total="300,00", c5_itens=[documento.Item(descricao="Consulta", codigo_tuss="99999999", valor="300,00")]),
        TEXTO)
    assert m["c6_valor_total"] is None and "C6" in m["campos_faltando"]
    assert m["c5_itens"][0]["codigo_tuss"] is None and m["avisos"]


def test_codigo_vazio_de_item_unico_vem_do_texto():
    m = documento.conferir("anexo_01", "CONSULTA_MEDICA", _molde(
        c5_itens=[documento.Item(descricao="Consulta médica", codigo_tuss=None, valor="250,00")]), TEXTO)
    assert m["c5_itens"][0]["codigo_tuss"] == "TUSS-10101012"


def test_valor_com_ponto_decimal_e_reconhecido_no_texto():
    m = documento.conferir("anexo_01", "CONSULTA_MEDICA", _molde(
        c6_valor_total="250.00", c5_itens=[documento.Item(descricao="Consulta", codigo_tuss="10101012", valor="250.00")]),
        TEXTO)
    assert m["c6_valor_total"] == 250.0 and m["c5_itens"][0]["valor"] == 250.0 and "C6" not in m["campos_faltando"]


def test_item_unico_sem_valor_recebe_o_total():
    m = documento.conferir("anexo_01", "CONSULTA_MEDICA", _molde(
        c5_itens=[documento.Item(descricao="Consulta médica", codigo_tuss="10101012", valor=None)]), TEXTO)
    assert m["c5_itens"][0]["valor"] == 250.0 and "C6" not in m["campos_faltando"]


def test_linha_de_assinatura_conta_como_assinatura():
    m = documento.conferir("anexo_01", "CONSULTA_MEDICA", _molde(c7_assinatura=False), TEXTO)
    assert "C7" not in m["campos_faltando"]


def test_campos_ausentes_viram_pendencia():
    m = documento.conferir("anexo_01", "CONSULTA_MEDICA", _molde(c3_registro_conselho=None, c1_beneficiario_cpf=None),
                           TEXTO)
    assert {"C1", "C3"} <= set(m["campos_faltando"]) and len(m["pendencias"]) == len(m["campos_faltando"])
    assert {"P02", "P06"} <= set(m["pendencias"])   # o código da ocorrência: CPF ausente é P02, não o P01 do nome


def test_data_de_cada_sessao_vem_do_texto():
    texto = TEXTO + "\nSessões: 04/03/2026 R$ 125,00; 11/03/2026 R$ 125,00"
    m = documento.conferir("anexo_01", "SESSAO_TERAPIA", _molde(c6_valor_total="250,00", c5_itens=[
        documento.Item(descricao="Sessão", valor="125,00", data="04/03/2026"),
        documento.Item(descricao="Sessão", valor="125,00", data="18/03/2026")]), texto)
    assert [i["data"] for i in m["c5_itens"]] == ["2026-03-04", None]   # data que não está no texto sai


@pytest.mark.parametrize("nome, cadastro, outra", [
    ("Ana Souza Lima", "ANA SOUZA LIMA", False), ("Âna Souza Lima", "Ana Souza Lima", False),
    ("Bruno Lima", "Ana Souza Lima", True), ("Bruno Lima", None, False), (None, "Ana Souza Lima", False),
])
def test_paciente_de_outra_pessoa(nome, cadastro, outra):
    assert documento.de_outra_pessoa({"c1_beneficiario_nome": nome}, cadastro) == outra


def test_situacao_do_anexo():
    valido = {"hash": "a", "molde": {"classificacao": "CONSULTA_MEDICA", "documento_fiscal": True}}
    relatorio = {"hash": "b", "molde": {"classificacao": "RELATORIO_CLINICO", "documento_fiscal": False}}
    recibo_de_relatorio = {"hash": "c", "molde": {"classificacao": "RELATORIO_CLINICO", "documento_fiscal": True}}
    invalido = {"hash": "d", "molde": documento.invalido("anexo_04", "conta de luz")}
    assert documento.situar(valido, []) == "ativo"
    assert documento.situar(valido, [valido]) == "duplicado"
    assert documento.situar(relatorio, []) == "complementar"
    assert documento.situar(recibo_de_relatorio, []) == "ativo"
    assert documento.situar(invalido, []) == "invalido"


# ------------------------------------------------------------------ carteirinhas
@pytest.mark.parametrize("texto, achadas", [
    ("7042 1111 2222 3333", ["7042111122223333"]), ("7042-1111-2222-3333", ["7042111122223333"]),
    ("7042.1111.2222.3333", ["7042111122223333"]), ("7042111122223333", ["7042111122223333"]),
    ("a dela é [carteirinha de outra pessoa]", []), ("7042 1111 2222 333", []), ("70421111222233334", []),
    ("minha 7042 1111 2222 3333 e a dele 7042 4444 5555 6666", ["7042111122223333", "7042444455556666"]),
])
def test_carteirinhas(texto, achadas):
    assert carteirinhas(texto) == achadas


def test_carteirinha_de_outra_pessoa_sai_do_texto():
    texto = "A minha é 7042 1111 2222 3333 e a dele é 7042-4444-5555-6666."
    dele = Carteirinha(numero="7042444455556666", dono="outra pessoa")
    assert acertar_carteirinhas(texto, texto, [dele]) == \
        "A minha é 7042 1111 2222 3333 e a dele é [carteirinha de outra pessoa]."
    assert acertar_carteirinhas(texto, texto, []) == texto


def test_reescrita_que_inventa_carteirinha_e_descartada(monkeypatch):
    from app.agents import reescrita

    monkeypatch.setattr(reescrita, "estruturado", lambda *a, **k: reescrita.Reescrita(
        mensagem="5310 7788 2401 9966.", carteirinhas=[]))
    out = reescrita.reescrever({"mensagens": [HumanMessage("7042 8813 5561 0029", id="m")], "pedidos": []})
    assert out["mensagens"][0].content == "7042 8813 5561 0029"


def test_carteirinha_do_cliente_esquecida_pela_reescrita_volta():
    original = "peraí... 7042 1111 2222 3333, é esse do cartão"
    minha = Carteirinha(numero="7042 1111 2222 3333", dono="o próprio cliente")
    assert acertar_carteirinhas("Espera, é este o número do cartão.", original, [minha]) == \
        "Espera, é este o número do cartão. Minha carteirinha é 7042 1111 2222 3333."
    # número que não estava na mensagem não entra
    inventada = Carteirinha(numero="7042 9999 9999 9999", dono="o próprio cliente")
    assert acertar_carteirinhas("Espera.", original, [inventada]) == "Espera."


# ------------------------------------------------------------------ ciclo de vida dos pedidos
def _p(pid, tipo, situacao, decisao=None):
    return {"id": pid, "tipo": tipo, "descricao": "x", "situacao": situacao, "na_rodada": True,
            "resultado": {"decisao": decisao} if decisao else None}


def test_rodada_nova_reabre_o_que_aguardava_o_cliente():
    pedidos = nova_rodada([_p("1.1", "reembolso", "aguardando_cliente"), _p("1.2", "duvida_regra", "atendido")])
    assert [(p["situacao"], p["na_rodada"]) for p in pedidos] == [("pendente", False), ("atendido", False)]


def test_responder_so_depois_do_arquivo_lido_e_das_duvidas_atendidas():
    msgs = {"mensagens": [HumanMessage("Segue o recibo.")]}
    assert "arquivo novo" in antes_de_responder({**msgs, "anexo": {"filename": "a.pdf"}}, [])
    assert "1.1" in antes_de_responder(msgs, [_p("1.1", "duvida_regra", "pendente")])
    # pergunta sem registro não vai direto à resposta: registrar_pedidos vem antes (lista vazia se não há pedido)
    assert "registrar_pedidos" in antes_de_responder(msgs, [])
    registrou = {"mensagens": [*msgs["mensagens"], AIMessage("", tool_calls=[
        {"name": "registrar_pedidos", "args": {"pedidos": []}, "id": "r1"}])]}
    assert antes_de_responder(registrou, [_p("1.1", "duvida_regra", "atendido"), _p("1.2", "reembolso", "pendente")]) is None
    # reembolso sem decisão, com documento e cliente identificado, passa pela decisão antes da resposta (D90)
    doc = {"documentos": [{"id": "anexo_01", "situacao": "ativo", "molde": {"classificacao": "CONSULTA_MEDICA"}}],
           "beneficiario": {"plano": "Pleno"}}
    assert "ag_normas" in antes_de_responder({**registrou, **doc}, [_p("1.1", "reembolso", "pendente")])
    assert antes_de_responder({**registrou, **doc}, [_p("1.1", "reembolso", "pendente", "APROVADO")]) is None
    decidiu = {**registrou, **doc, "mensagens": [*registrou["mensagens"], ToolMessage("x", tool_call_id="n1", name="ag_normas")]}
    assert antes_de_responder(decidiu, [_p("1.1", "reembolso", "pendente")]) is None
    maliciosa = {"mensagens": [HumanMessage("[mensagem maliciosa] x")], "anexo": {"filename": "a.pdf"}}
    assert antes_de_responder(maliciosa, []) is None
    # carteirinha na mensagem e cliente não identificado: a triagem vem antes, em código
    cartao = {"mensagens": [HumanMessage("A carteirinha é 7042 1111 2222 3333.")]}
    assert falta_triagem(cartao) and not falta_triagem({**cartao, "beneficiario": {"plano": "Pleno"}})
    assert not falta_triagem({"mensagens": [HumanMessage("[mensagem maliciosa] 7042 1111 2222 3333")]})


def test_data_de_emissao_e_linhas_de_item_do_texto():
    assert documento.data_de_emissao("Paciente: X\nData da solicitação: 20/04/2026\nDr. Y") == "2026-04-20"
    assert documento.data_de_emissao("Relatório\nemitido em São Paulo, 02/05/2026") == "2026-05-02"
    assert documento.data_de_emissao("Paciente: X\nExame: Y") is None
    linhas = documento.linhas_de_item("Valor total: R$ 890,00\nItem 1: Armação de óculos - R$ 390,00\nItem 2: Lentes - R$ 500,00")
    assert "Armação de óculos" in linhas and "Lentes" in linhas and "890" not in linhas


def test_arquivo_que_o_modelo_nao_leu_e_lido_pelo_codigo(monkeypatch):
    from app.agents import supervisor as sup

    monkeypatch.setattr(sup, "chamar", lambda estado, pedidos: None)   # o modelo esgota as tentativas
    atendida = {**_p("1.1", "duvida_regra", "atendido"), "rodada": 1}
    estado = {"mensagens": [HumanMessage("dúvida"), AIMessage("resposta"),
                            HumanMessage("o recibo tá aqui [arquivo anexado: r.pdf]")],
              "pedidos": [atendida], "anexo": {"filename": "r.pdf"}, "beneficiario": {"plano": "Pleno"}}
    out = sup.supervisor(estado)
    leitura = out["mensagens"][-1].tool_calls[0]
    novo = next(p for p in out["pedidos"] if p["id"] == leitura["args"]["pedido_id"])
    assert leitura["name"] == "ag_documento" and novo["tipo"] == "reembolso" and novo["situacao"] == "pendente"
    sem_texto = {**estado, "mensagens": [HumanMessage("[arquivo anexado: r.pdf]")], "pedidos": []}
    out = sup.supervisor(sem_texto)
    assert out["pedidos"][-1]["tipo"] == "documento"


def test_carteirinha_nova_vai_para_a_triagem_sem_passar_pelo_modelo(monkeypatch):
    from app.agents import supervisor as sup

    monkeypatch.setattr(sup, "chamar", lambda *a: pytest.fail("chamou o modelo"))
    out = sup.supervisor({"mensagens": [HumanMessage("A minha é 7042 1111 2222 3333.")], "pedidos": []})
    assert out["mensagens"][0].tool_calls[0]["name"] == "ag_triagem" and sup.rota(out) == "ag_triagem"


def test_encerrar_mensagem():
    pedidos = [_p("1.1", "reembolso", "pendente", "PENDENTE_DOCUMENTO"), _p("1.2", "reembolso", "pendente"),
               _p("1.3", "reembolso", "pendente", "APROVADO"), _p("1.4", "duvida_regra", "pendente"),
               _p("1.5", "terceiro", "inviavel")]
    _encerrar(pedidos)
    assert [p["situacao"] for p in pedidos] == ["aguardando_cliente", "pendente", "atendido", "atendido", "inviavel"]


# ------------------------------------------------------------------ estado
def test_desta_mensagem_e_documentos():
    msgs = [HumanMessage("a"), AIMessage("r"), HumanMessage("b"),
            AIMessage("", tool_calls=[{"name": "ag_triagem", "args": {}, "id": "1"}]),
            ToolMessage("ok", tool_call_id="1", name="ag_triagem")]
    assert [m.type for m in desta_mensagem({"mensagens": msgs})] == ["ai", "tool"]
    docs = [{"id": "anexo_01", "situacao": "substituido"}, {"id": "anexo_02", "situacao": "ativo"},
            {"id": "anexo_03", "situacao": "complementar"}]
    assert documento_ativo({"documentos": docs})["id"] == "anexo_02"
    assert [d["id"] for d in complementares({"documentos": docs})] == ["anexo_03"]


# ------------------------------------------------------------------ dados da resposta
def test_dados_quando_a_mensagem_so_identifica_o_cliente():
    msgs = [HumanMessage("7042 1111 2222 3333"),
            AIMessage("", tool_calls=[{"name": "ag_triagem", "args": {}, "id": "1"}]),
            ToolMessage("cliente identificado", tool_call_id="1", name="ag_triagem")]
    dados = responder._dados({"mensagens": msgs, "pedidos": [], "documentos": [],
                              "beneficiario": {"plano": "Pleno", "status": "ATIVO", "data_adesao": "2024-01-01"}})
    assert "identificado" in dados and "Pleno" in dados


def test_dados_levam_o_reembolso_decidido_mesmo_sem_ser_desta_mensagem():
    reembolso = {**_p("1.1", "reembolso", "atendido", "APROVADO"), "na_rodada": False}
    reembolso["resultado"].update(valor_reembolso=60.0, memoria=["o teto não limitou o valor"], regras=["ART-44"])
    duvida = _p("2.1", "duvida_regra", "atendido")
    dados = responder._dados({"mensagens": [HumanMessage("x")], "pedidos": [reembolso, duvida], "documentos": []})
    assert "o teto não limitou" in dados and "decisão APROVADO" in dados


def test_prazo_para_pedir_sai_antes_da_decisao(monkeypatch):
    from app.decisao import prazo_sem_decisao

    molde = {"c4_data_atendimento": "2026-02-02", "c5_itens": [{"data": None}]}
    assert "107 dias" in prazo_sem_decisao(molde, date(2026, 5, 20)) and "já passou" in prazo_sem_decisao(molde, date(2026, 5, 20))
    assert "dentro do prazo" in prazo_sem_decisao({**molde, "c5_itens": [{"data": "2026-05-04"}]}, date(2026, 5, 20))
    assert prazo_sem_decisao({"c5_itens": []}, date(2026, 5, 20)) is None
    monkeypatch.setenv("DATA_REFERENCIA", "2026-05-20")
    doc = {"id": "anexo_01", "rodada": 1, "situacao": "ativo", "arquivo": "r.pdf",
           "molde": {"classificacao": "CONSULTA_MEDICA", "c4_data_atendimento": "2026-02-02", "c5_itens": []}}
    dados = responder._dados({"mensagens": [HumanMessage("x")], "pedidos": [_p("1.1", "reembolso", "pendente")],
                              "documentos": [doc]})
    assert "sem decisão" in dados and "o prazo já passou" in dados


def test_dados_lembram_o_pedido_sobre_outra_pessoa_feito_antes():
    terceiro = {**_p("1.1", "terceiro", "inviavel"), "na_rodada": False, "motivo": "pedido sobre outra pessoa"}
    duvida = _p("2.1", "duvida_regra", "atendido")
    dados = responder._dados({"mensagens": [HumanMessage("x")], "pedidos": [terceiro, duvida], "documentos": []})
    assert "nada dessa pessoa é processado neste atendimento" in dados
    assert "nada dessa pessoa" not in responder._dados({"mensagens": [HumanMessage("x")], "pedidos": [duvida],
                                                         "documentos": []})


def test_dados_da_situacao_de_pedido_anterior_trazem_o_historico():
    status = _p("1.1", "status_pedido", "atendido")
    status["resultado"] = {"norma": "", "historico": [{"protocolo": "20260000099", "data_atendimento": "2026-03-02",
                                                       "categoria": "EXAME_DIAGNOSTICO", "decisao": "APROVADO",
                                                       "valor_reembolsado": "80.5"}]}
    dados = responder._dados({"mensagens": [HumanMessage("x")], "pedidos": [status], "documentos": []})
    assert "protocolo 20260000099" in dados and "exame diagnóstico, decisão APROVADO" in dados and "R$ 80.5" in dados
    status["resultado"]["historico"] = []
    assert "nenhum pedido anterior" in responder._dados({"mensagens": [HumanMessage("x")], "pedidos": [status],
                                                         "documentos": []})


def test_dados_do_pedido_inviavel_e_do_anexo_invalido():
    inviavel = {**_p("1.1", "terceiro", "inviavel"), "motivo": "pedido sobre outra pessoa"}
    anexo = {"id": "anexo_01", "rodada": 1, "situacao": "invalido", "molde": documento.invalido("anexo_01", "conta de luz")}
    dados = responder._dados({"mensagens": [HumanMessage("x")], "pedidos": [inviavel], "documentos": [anexo]})
    assert "pedido sobre outra pessoa" in dados and "inválido (conta de luz)" in dados


def test_revisor_nao_deixa_resposta_curta_demais(monkeypatch):
    monkeypatch.setattr(responder, "_revisar", lambda estado, rascunho: "Certo.")
    rascunho = AIMessage("Certo. Assim que você enviar o documento, eu dou andamento ao pedido.", id="r1")
    assert responder.revisar({"mensagens": [HumanMessage("ok"), rascunho], "pedidos": []}) == {}


def test_prompts_da_resposta_e_do_revisor_montam():
    # os dois levam as leituras da norma e não sobra chave sem preencher
    sistema = responder.SISTEMA.format(dados="x", leituras=responder.LEITURAS)
    revisar = responder.REVISAR.format(dados="x", mensagem="y", rascunho="z", leituras=responder.LEITURAS)
    for texto in (sistema, revisar):
        assert "profissional assistente" in texto and "{" not in texto


def test_log_local_grava_no_prompt_resposta_e_raciocinio(tmp_path, monkeypatch):
    import json

    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

    from app.llm import _log_local

    arquivo = tmp_path / "chamadas.jsonl"
    monkeypatch.setenv("LOG_LLM", str(arquivo))
    llm = GenericFakeChatModel(messages=iter([AIMessage(content="ok", additional_kwargs={"reasoning_content": "pensei"})]),
                               callbacks=[_log_local()])
    llm.invoke([HumanMessage(content="oi")], {"metadata": {"langgraph_node": "responder"}})
    linha = json.loads(arquivo.read_text(encoding="utf-8"))
    assert (linha["no"], linha["prompt"][0]["conteudo"], linha["resposta"], linha["raciocinio"]) == \
        ("responder", "oi", "ok", "pensei")


def test_duvida_com_reembolso_decidido_leva_os_artigos_da_decisao():
    from app.agents.normas import _fundamentos_da_decisao

    estado = {"pedidos": [{"id": "1.1", "tipo": "reembolso", "resultado": {"decisao": "NEGADO",
                                                                          "regras": ["TUSS-40301082", "ART-45"]}}],
              "documentos": [], "mensagens": []}
    texto = _fundamentos_da_decisao(estado, "")
    assert "Art. 45 (fundamento da decisão do reembolso)" in texto and "todas as categorias" in texto
    assert _fundamentos_da_decisao(estado, "### x\nCitar: ART-45\n...") == ""   # já veio na busca: não repete


def test_nome_do_paciente_que_nao_esta_no_texto_sai_do_molde():
    m = documento.conferir("anexo_01", "CONSULTA_MEDICA", _molde(c1_beneficiario_nome="Outra Pessoa Qualquer"), TEXTO)
    assert m["c1_beneficiario_nome"] is None and "C1" in m["campos_faltando"]
    assert documento.conferir("anexo_01", "CONSULTA_MEDICA", _molde(c1_beneficiario_nome="ANA SOUZA LIMA"),
                              TEXTO)["c1_beneficiario_nome"] == "ANA SOUZA LIMA"


def test_indicacao_clinica_so_vale_com_o_trecho_que_a_traz():
    texto = TEXTO + "\nIndicação: pós-operatório de cirurgia do joelho, para tratamento do edema."
    sem_trecho = documento.conferir("anexo_01", "CONSULTA_MEDICA", _molde(c10_indicacao_clinica=True), TEXTO)
    so_o_nome = documento.conferir("anexo_01", "CONSULTA_MEDICA", _molde(c10_indicacao_clinica=True,
                                   c10_trecho="Consulta médica"), TEXTO)
    com_trecho = documento.conferir("anexo_01", "CONSULTA_MEDICA", _molde(
        c10_indicacao_clinica=True, c10_trecho="pós-operatório de cirurgia do joelho, para tratamento do edema"), texto)
    assert not sem_trecho["c10_indicacao_clinica"] and not so_o_nome["c10_indicacao_clinica"]
    assert com_trecho["c10_indicacao_clinica"] and "c10_trecho" not in com_trecho   # o trecho não fica no estado

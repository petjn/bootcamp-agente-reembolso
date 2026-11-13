"""Triagem (sem MCP de verdade) e filtro de saída.

O filtro usa os mesmos padrões da checagem objetiva da avaliação, que reprova o
turno inteiro; por isso cada armadilha conhecida tem um teste.
"""

from langchain_core.messages import AIMessage, HumanMessage

from app import tools
from app.agents import triagem
from app.agents.estado import terceiros
from app.guardrails import CID, CPF, filtrar, formatar_protocolo, repetida


# ------------------------------------------------------------------ filtro de saída
def test_protocolo_do_mcp_nao_sai_como_cpf():
    assert CPF.search("Seu protocolo é 20260000001.")          # a armadilha
    saida = filtrar("Seu protocolo é 20260000001.", protocolos=["20260000001"]).texto
    assert saida == "Seu protocolo é 2026-0000001." and not CPF.search(saida)
    assert formatar_protocolo("20260000001") == "2026-0000001"


def test_cpf_completo_e_mascarado():
    saida = filtrar("O CPF 528.417.930-11 consta no recibo.").texto
    assert "528.417.930-11" not in saida and "***.417.930-**" in saida


def test_codigos_de_campo_e_pendencia_nao_saem_porque_parecem_cid():
    assert CID.search("falta o campo C10") and CID.search("pendência P02")
    saida = filtrar("Falta o campo C10 (pendência P02).").texto
    assert not CID.search(saida)


def test_carteirinha_de_terceiro_some_em_qualquer_formato():
    for forma in ("7042 5199 0887 3310", "7042519908873310", "7042-5199-0887-3310"):
        saida = filtrar(f"A carteirinha {forma} não pode ser consultada.", terceiros=["7042519908873310"]).texto
        assert "7042519908873310" not in "".join(ch for ch in saida if ch.isdigit())


def test_resposta_repetida():
    assert repetida("Recebi o seu recibo.", ["Olá!", "Recebi  o seu\nrecibo."])
    assert not repetida("Recebi o seu recibo, obrigado.", ["Recebi o seu recibo."])


# ------------------------------------------------------------------ cliente MCP
def test_sessoes_nos_esquemas_v1_e_v2():
    assert tools._sessoes({"sessoes_terapia_ano": 4}) == 4
    assert tools._sessoes({"sessoes_terapia": {"ano_corrente": 4, "acumulado": 30}}) == 4
    assert tools._sessoes({}) is None


# ------------------------------------------------------------------ triagem
# A triagem lê o pedido nos argumentos da chamada do supervisor (nas mensagens) e devolve uma ToolMessage.
def _pedido(tipo="dados_cadastro", pid="1.carteirinha"):
    return {"id": pid, "tipo": tipo, "descricao": "x", "situacao": "pendente", "na_rodada": True}


def _estado(msg, pedido=None, **extra):
    p = pedido or _pedido()
    chamada = AIMessage("", tool_calls=[{"name": "ag_triagem", "args": {"pedido_id": p["id"]}, "id": "c1"}])
    return {"mensagens": [HumanMessage(msg), chamada], "pedidos": [p], **extra}


def test_primeira_carteirinha_abre_a_sessao(monkeypatch):
    consultadas = []
    monkeypatch.setattr(triagem, "_consultar",
                        lambda c: consultadas.append(c) or {"plano": "Pleno", "carteirinha": c})
    out = triagem.ag_triagem(_estado("7042 8813 5561 0029"))
    assert out["mensagens"][0].tool_call_id == "c1"
    assert out["beneficiario"]["carteirinha"] == "7042881355610029" and consultadas == ["7042881355610029"]
    assert out["pedidos"][0]["situacao"] == "atendido"


def test_carteirinha_nao_localizada_aguarda_o_cliente(monkeypatch):
    def falha(c):
        raise tools.ErroMCP("beneficiário não localizado para a carteirinha")
    monkeypatch.setattr(triagem, "_consultar", falha)
    out = triagem.ag_triagem(_estado("0000 0000 0000 0000"))
    p = out["pedidos"][0]
    assert "beneficiario" not in out
    assert p["situacao"] == "aguardando_cliente" and "não foi localizada" in p["motivo"]


def test_triagem_nao_consulta_carteirinha_mascarada_pela_reescrita(monkeypatch):
    consultadas = []
    monkeypatch.setattr(triagem, "_consultar", lambda c: consultadas.append(c) or {})
    estado = _estado("x", _pedido("reembolso", "2.1"))
    estado["mensagens"][0] = HumanMessage("A carteirinha dela é [carteirinha de outra pessoa]. Dá para ver o dela?")
    p = triagem.ag_triagem(estado)["pedidos"][0]
    assert consultadas == [] and p["situacao"] == "aguardando_cliente"


def test_terceiros_vem_do_historico():
    estado = _estado("a carteirinha dela é 7042 5199 0887 3310", beneficiario={"carteirinha": "7042881355610029"})
    assert terceiros(estado) == ["7042519908873310"]


def test_sem_carteirinha_o_pedido_aguarda_e_diz_o_que_falta(monkeypatch):
    monkeypatch.setattr(triagem, "_consultar", lambda c: {})
    out = triagem.ag_triagem(_estado("quero reembolso", _pedido("reembolso", "1.1")))
    p = out["pedidos"][0]
    assert p["situacao"] == "aguardando_cliente" and "carteirinha" in p["motivo"]
    assert "carteirinha" in out["mensagens"][0].content   # o que falta volta ao supervisor na ToolMessage

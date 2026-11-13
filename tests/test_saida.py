"""Nível 0: a saída do /chat (`grafo.saida`) em cada tipo de desfecho, como o avaliador a compara."""

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.estado import assinatura
from app.agents.grafo import saida


def _estado(pedidos, documentos=()):
    return {"mensagens": [HumanMessage("x"), AIMessage("resposta")], "pedidos": list(pedidos),
            "documentos": list(documentos)}


def _reembolso(decisao, **res):
    estado = _estado([])
    return {"id": "1.1", "tipo": "reembolso", "descricao": "x", "situacao": "atendido", "na_rodada": False,
            "assinatura": assinatura(estado),
            "resultado": {"decisao": decisao, "categoria": "CONSULTA_MEDICA", "valor_solicitado": 100.0,
                          "regras": ["ART-44"], **res}}


def test_aprovado_leva_valor_e_nao_leva_protocolo():
    r = saida(_estado([_reembolso("APROVADO", valor_reembolso=60.0, protocolo="20260000001")]))
    assert (r.decisao, float(r.valor_reembolso_brl), r.protocolo) == ("APROVADO", 60.0, None)


def test_negado_sai_com_valor_zero():
    r = saida(_estado([_reembolso("NEGADO")]))
    assert r.decisao == "NEGADO" and float(r.valor_reembolso_brl) == 0.0


def test_pendente_e_escalado_levam_o_protocolo():
    for decisao in ("PENDENTE_DOCUMENTO", "ESCALADO_ANALISTA"):
        r = saida(_estado([_reembolso(decisao, protocolo="20260000007")]))
        assert r.protocolo and r.valor_reembolso_brl is None


def test_terceiro_sem_pedido_proprio_fica_fora_de_escopo_ate_o_fim():
    terceiro = {"id": "1.1", "tipo": "terceiro", "descricao": "x", "situacao": "inviavel", "na_rodada": False}
    r = saida(_estado([terceiro]))
    assert r.decisao == "FORA_DE_ESCOPO" and r.regras_aplicadas == ["ART-8"]


def test_terceiro_nao_muda_o_desfecho_do_pedido_proprio():
    terceiro = {"id": "4.1", "tipo": "terceiro", "descricao": "x", "situacao": "inviavel", "na_rodada": True}
    r = saida(_estado([_reembolso("APROVADO", valor_reembolso=60.0), terceiro]))
    assert r.decisao == "APROVADO"


def test_assunto_alheio_nao_tem_decisao():
    alheio = {"id": "2.1", "tipo": "outro", "descricao": "x", "situacao": "inviavel", "na_rodada": True}
    r = saida(_estado([alheio]))
    assert r.decisao is None and r.regras_aplicadas == []


def test_sem_pedido_nada_e_preenchido():
    r = saida(_estado([]))
    assert (r.decisao, r.categoria_documento, r.valor_reembolso_brl, r.protocolo) == (None, None, None, None)

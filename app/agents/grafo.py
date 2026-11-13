"""O grafo do agente: os nós, as arestas e a memória das sessões.

Cada mensagem do cliente percorre:

    START -> reescrever -> supervisor <-> ag_triagem
                                      <-> ag_documento
                                      <-> ag_normas
                           supervisor -> responder -> revisar -> END

O supervisor só chama o modelo; a aresta condicional `rota` (em supervisor.py) lê a chamada
e manda para o agente, ou para a resposta quando não há chamada. Cada agente devolve a vez
ao supervisor com uma ToolMessage. O estado é persistido por `session_id`.
"""

from __future__ import annotations

from functools import cache

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.documento import ag_documento
from app.agents.estado import Estado, assinatura
from app.agents.normas import ag_normas
from app.agents.reescrita import reescrever
from app.agents.responder import _reembolso, responder, revisar
from app.agents.supervisor import AGENTES, rota, supervisor
from app.agents.triagem import ag_triagem
from app.schemas import ChatResponse


def construir(checkpointer=None):
    g = StateGraph(Estado)
    g.add_node("reescrever", reescrever)
    g.add_node("supervisor", supervisor)
    g.add_node("ag_triagem", ag_triagem)
    g.add_node("ag_documento", ag_documento)
    g.add_node("ag_normas", ag_normas)
    g.add_node("responder", responder)
    g.add_node("revisar", revisar)   # reflexão: confere a resposta contra os dados antes de enviar (D45)
    g.add_edge(START, "reescrever")
    g.add_edge("reescrever", "supervisor")
    g.add_conditional_edges("supervisor", rota, [*AGENTES, "responder"])
    for agente in AGENTES:   # cada agente devolve a vez ao supervisor, com uma ToolMessage
        g.add_edge(agente, "supervisor")
    g.add_edge("responder", "revisar")
    g.add_edge("revisar", END)
    return g.compile(checkpointer=checkpointer, name="agente_reembolso")


@cache
def grafo():
    """O grafo compilado com a memória das sessões. `reset()` limpa."""
    return construir(InMemorySaver())


def saida(estado: Estado) -> ChatResponse:
    """O ChatResponse sai do pedido de reembolso e dos documentos; nada disso fica
    duplicado no estado. A decisão só vale se foi tomada com os dados atuais."""
    p = _reembolso(estado) or {}
    res = (p.get("resultado") or {}) if p.get("assinatura") == assinatura(estado) else {}
    # pedido sobre outra pessoa (art. 8º): sem pedido próprio decidido, o desfecho da conversa é FORA_DE_ESCOPO
    terceiro = any(x["tipo"] == "terceiro" and x["situacao"] == "inviavel" for x in estado.get("pedidos", []))
    decisao = res.get("decisao") or ("FORA_DE_ESCOPO" if terceiro else None)
    regras = res.get("regras", []) if res.get("decisao") else (["ART-8"] if terceiro else [])
    categoria = res.get("categoria")
    if not categoria and estado.get("documentos"):
        ultimo = estado["documentos"][-1]
        categoria = ultimo["molde"]["classificacao"]
    aprovado = decisao in ("APROVADO", "APROVADO_PARCIAL")
    ultima = next((m.content for m in reversed(estado.get("mensagens", [])) if m.type == "ai"), "")
    return ChatResponse(resposta=ultima, categoria_documento=categoria, decisao=decisao,
                        valor_solicitado_brl=res.get("valor_solicitado"),
                        valor_reembolso_brl=res.get("valor_reembolso") if aprovado else (0.0 if decisao == "NEGADO" else None),
                        regras_aplicadas=regras,
                        # o protocolo fica aberto enquanto o pedido espera o cliente ou o analista (arts. 18 e 78)
                        protocolo=res.get("protocolo") if decisao in ("PENDENTE_DOCUMENTO", "ESCALADO_ANALISTA") else None,
                        pendencias=res.get("pendencias", []))


def turno(session_id: str, mensagem: str, anexo: dict | None = None) -> ChatResponse:
    estado = grafo().invoke({"mensagens": [HumanMessage(mensagem or "")], "anexo": anexo},
                            config={"configurable": {"thread_id": session_id}, "recursion_limit": 60,
                                    "run_name": "turno", "metadata": {"session_id": session_id}})
    return saida(estado)


def reset() -> None:
    grafo.cache_clear()

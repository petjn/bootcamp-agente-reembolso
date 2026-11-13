"""Estado da sessão: a ficha de atendimento que todos os nós leem e anotam.

O avaliador manda só a mensagem nova e o `session_id`; o resto vem do checkpointer.

Como nos exemplos do LangGraph (pasta `referencia/`), a conversa fica em `mensagens`: as
mensagens do cliente (já reescritas), as chamadas do supervisor (AIMessage com
`tool_calls`), o que cada agente devolveu (ToolMessage) e as respostas ao cliente. Os
pedidos ficam em `pedidos`, registrados pelo supervisor, com a situação e o resultado de
cada um. Cada arquivo enviado fica em `documentos`, com o molde preenchido.
"""

from __future__ import annotations

from typing import Annotated, Literal

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

TipoPedido = Literal["reembolso", "documento", "duvida_regra", "status_pedido", "dados_cadastro", "terceiro",
                     "outro"]


class Estado(TypedDict, total=False):
    """Cinco campos. O resto se deriva: a rodada vem das mensagens; a saída do /chat vem do
    pedido de reembolso e dos documentos."""

    mensagens: Annotated[list[AnyMessage], add_messages]   # a conversa, com as chamadas e os retornos
    anexo: dict | None                  # leva o arquivo do /chat ao ag_documento; apagado depois da leitura
    pedidos: list[dict]                 # o centro do atendimento: situação e resultado de cada pedido
    beneficiario: dict | None           # cadastro do MCP, com a carteirinha que abriu a sessão
    documentos: list[dict]              # cada anexo, com o molde válido ou inválido


def rodada(estado: Estado) -> int:
    """Número da mensagem do cliente (1, 2, 3...), contado no histórico."""
    return sum(1 for m in estado.get("mensagens", []) if m.type == "human")


def carteirinha(estado: Estado) -> str | None:
    """A carteirinha que abriu a sessão: só vale depois que o MCP a reconheceu."""
    return (estado.get("beneficiario") or {}).get("carteirinha")


def terceiros(estado: Estado) -> list[str]:
    """Carteirinhas citadas na conversa que não são a da sessão (art. 8º): nunca repetidas
    na resposta. Vêm do histórico."""
    from app.agents.triagem import carteirinhas

    humanas = [m.content for m in estado.get("mensagens", []) if m.type == "human"]
    propria = carteirinha(estado)
    if not propria:
        return carteirinhas(humanas[-1])[1:] if humanas else []
    citadas = dict.fromkeys(c for texto in humanas for c in carteirinhas(texto))
    return [c for c in citadas if c != propria]


def condicoes(estado: Estado) -> list[str]:
    """Condições de saúde que o cliente contou na conversa, anotadas pela reescrita em cada mensagem dele: nunca
    repetidas na resposta (art. 7º). Vêm do histórico."""
    from app.guardrails import termos_de_condicao

    return termos_de_condicao([c for m in estado.get("mensagens", []) if m.type == "human"
                               for c in m.additional_kwargs.get("condicoes", [])])


def desta_mensagem(estado: Estado) -> list[AnyMessage]:
    """As mensagens depois da última mensagem do cliente: as chamadas e os retornos desta rodada."""
    msgs = estado.get("mensagens", [])
    ultima = max((i for i, m in enumerate(msgs) if m.type == "human"), default=-1)
    return msgs[ultima + 1:]


def chamadas_na_rodada(estado: Estado) -> int:
    """Quantas vezes o supervisor chamou uma ferramenta nesta mensagem (teto contra laço infinito)."""
    return sum(1 for m in desta_mensagem(estado) if m.type == "ai" and m.tool_calls)


def chamada(estado: Estado) -> tuple[str, dict]:
    """(id, argumentos) da última chamada do supervisor: é assim que o agente sabe o que fazer,
    como nos exemplos do LangGraph (o nó lê tool_calls[0]["args"] da última mensagem)."""
    ultima = next(m for m in reversed(estado.get("mensagens", [])) if m.type == "ai" and m.tool_calls)
    return ultima.tool_calls[0]["id"], ultima.tool_calls[0]["args"]


def pedido(pedidos: list[dict], pid: str | None) -> dict | None:
    return next((p for p in pedidos if p["id"] == pid), None)


def assinatura(estado: Estado) -> str:
    """O que a decisão do reembolso usa. Se mudar (documento novo, relatório que chegou,
    cadastro consultado), a decisão é refeita; se não mudar, não roda de novo."""
    doc = documento_ativo(estado)
    comps = sorted(d["id"] for d in complementares(estado))
    return f"{doc['id'] if doc else '-'}|{comps}|{bool(estado.get('beneficiario'))}"


def documento_ativo(estado: Estado) -> dict | None:
    """O documento fiscal válido mais recente que não foi substituído."""
    ativos = [d for d in estado.get("documentos", []) if d.get("situacao") == "ativo"]
    return ativos[-1] if ativos else None


def complementares(estado: Estado) -> list[dict]:
    """Relatórios e pedidos médicos: completam o documento fiscal."""
    return [d for d in estado.get("documentos", []) if d.get("situacao") == "complementar"]

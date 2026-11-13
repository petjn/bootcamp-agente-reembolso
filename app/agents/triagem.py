"""Triagem — carteirinha e elegibilidade do próprio cliente.

  * Carteirinha: lida na última mensagem do cliente, já reescrita, onde a carteirinha de
    outra pessoa vira "[carteirinha de outra pessoa]". A primeira carteirinha válida abre a sessão e não muda mais.
  * Elegibilidade: `consultar_beneficiario` (plano, adesão, situação, sessões). Plano e
    adesão vêm sempre do MCP, nunca do que a pessoa diz. O histórico de pedidos é
    consultado pelo ag_normas na hora de decidir, para sair fresco da fonte.

Pedido sobre outra pessoa (art. 8º) não chega aqui: o supervisor o registra como inviável
(trava no prompt dele), e nada dessa pessoa é consultado.
"""

from __future__ import annotations

import re

from langchain_core.messages import ToolMessage

from app.agents.estado import Estado, chamada, pedido
from app.tools import ErroMCP, consultar_beneficiario

# 16 dígitos, com ou sem separador a cada 4 ("5310 7788 2401 9966")
RE_CARTEIRINHA = re.compile(r"(?<!\d)(\d{4}[\s.-]?\d{4}[\s.-]?\d{4}[\s.-]?\d{4})(?!\d)")


def carteirinhas(texto: str) -> list[str]:
    return list(dict.fromkeys(re.sub(r"\D", "", m) for m in RE_CARTEIRINHA.findall(texto or "")))


def _consultar(numero: str) -> dict:
    """Cadastro do MCP, no formato do estado, com a carteirinha que abriu a sessão."""
    return {**consultar_beneficiario(numero).model_dump(mode="json", exclude={"bruto"}), "carteirinha": numero}


def ag_triagem(estado: Estado) -> dict:
    """Atende a chamada do supervisor (o pedido vem nos argumentos dela) e devolve o
    resultado numa ToolMessage, como os nós de ferramenta dos exemplos do LangGraph:
    identifica o cliente pela carteirinha da mensagem (MCP). Pedido que era só a carteirinha
    fica atendido; os outros seguem pendentes, já com o cliente identificado, e o que
    esperava só a carteirinha volta a pendente. Sem
    carteirinha, ou carteirinha não localizada, o pedido aguarda o cliente."""
    cid, args = chamada(estado)
    pedidos = [dict(p) for p in estado.get("pedidos", [])]
    p = pedido(pedidos, args.get("pedido_id")) or {}   # sem pedido: a carteirinha é um fato da mensagem
    update: dict = {"pedidos": pedidos}

    def devolve(texto: str) -> dict:
        return {**update, "mensagens": [ToolMessage(texto, tool_call_id=cid, name="ag_triagem")]}

    p["na_rodada"] = True
    b = estado.get("beneficiario")
    if not b:
        # a carteirinha vem da última mensagem do cliente, já reescrita: nela, a reescrita (prompt)
        # trocou a carteirinha de outra pessoa por "[carteirinha de outra pessoa]"
        ultima = next((m.content for m in reversed(estado.get("mensagens", [])) if m.type == "human"), "")
        achadas = carteirinhas(ultima)
        if not achadas:
            p.update(situacao="aguardando_cliente", motivo="informar o número da carteirinha")
            return devolve("a mensagem não traz a carteirinha do cliente; ele precisa informá-la")
        try:
            b = update["beneficiario"] = _consultar(achadas[0])
        except ErroMCP as erro:
            falta = ("conferir o número da carteirinha, que não foi localizada" if "não localizado" in str(erro)
                     else "tentar de novo em instantes: o cadastro da operadora não respondeu")
            p.update(situacao="aguardando_cliente", motivo=falta)
            return devolve(f"o cliente precisa {falta}")
    if p.get("tipo") == "dados_cadastro":
        p["situacao"] = "atendido"
    for outro in pedidos:
        # o pedido que esperava só a carteirinha volta a pendente para ser atendido nesta mensagem: sem isso, a
        # pergunta feita antes da carteirinha ficava sem resposta depois dela (D87). O reembolso se retoma pelo
        # registro do supervisor, que o junta ao existente
        if (outro["tipo"] != "reembolso" and outro["situacao"] == "aguardando_cliente"
                and outro.get("motivo") == "informar o número da carteirinha"):
            outro.update(situacao="pendente", motivo="", na_rodada=True)
    return devolve(f"cliente identificado (plano {b.get('plano')}, situação {b.get('status')})")
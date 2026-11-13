"""Ferramentas — cliente do servidor MCP.

Três ferramentas, por HTTP streamable, em `MCP_OPERADORA_URL`:

    consultar_beneficiario(carteirinha)   plano, adesão, sessões, situação
    consultar_historico(carteirinha)      pedidos de reembolso anteriores
    abrir_protocolo(carteirinha, payload) número de protocolo

O token de `MCP_OPERADORA_TOKEN` vai no header `Authorization`; sem ele o
servidor responde 401.

Dois detalhes que costumam derrubar cliente:

  * erro de ferramenta no MCP volta como `isError` no resultado, e **não** como
    exceção de transporte. Quem não olha esse campo trata "beneficiário não
    localizado" como se fosse resposta válida;
  * o formato do retorno pode mudar durante a prova. Escreva de forma que um
    campo com outra forma não derrube o fluxo inteiro.

Nada aqui guarda resposta em cache permanente: o cadastro muda entre o treino e
a avaliação. O endereço e o token vêm sempre do ambiente.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import date
from decimal import Decimal

from langsmith import traceable
from pydantic import BaseModel, Field

from app.llm import carregar_env


class ErroMCP(RuntimeError):
    """Erro devolvido pela ferramenta (isError) ou falha de transporte."""


class Beneficiario(BaseModel):
    carteirinha: str
    nome: str | None = None
    plano: str | None = None
    data_adesao: date | None = None
    status: str | None = None
    sessoes_terapia_ano: int | None = None
    cpf_mascarado: str | None = None
    bruto: dict = Field(default_factory=dict, description="o retorno original, para campos que ainda não usamos")


class PedidoAnterior(BaseModel):
    data: date | None = None
    categoria: str | None = None
    valor_reembolsado: Decimal = Decimal(0)
    protocolo: str | None = None
    decisao: str | None = None
    bruto: dict = Field(default_factory=dict)


class Historico(BaseModel):
    carteirinha: str
    pedidos: list[PedidoAnterior]

    def reembolsado_no_ano(self, ano: int) -> Decimal:
        return sum((p.valor_reembolsado for p in self.pedidos if p.data and p.data.year == ano), Decimal(0))


def _config() -> tuple[str, dict]:
    carregar_env()
    url = os.getenv("MCP_OPERADORA_URL", "").strip()
    if not url:
        raise ErroMCP("MCP_OPERADORA_URL não definido no ambiente")
    token = os.getenv("MCP_OPERADORA_TOKEN", "").strip()
    cabecalho = {"Authorization": token if token.lower().startswith("bearer ") else f"Bearer {token}"} if token else {}
    return url, cabecalho


async def _chamar(ferramenta: str, argumentos: dict) -> dict:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    url, cabecalho = _config()
    async with streamablehttp_client(url, headers=cabecalho, timeout=30) as (leitura, escrita, _):
        async with ClientSession(leitura, escrita) as sessao:
            await sessao.initialize()
            r = await sessao.call_tool(ferramenta, argumentos)
    texto = " ".join(getattr(c, "text", "") for c in r.content or [])
    if r.isError:
        raise ErroMCP(texto or f"erro em {ferramenta}")
    if r.structuredContent:
        dados = r.structuredContent
        # o FastMCP embrulha retorno não-objeto em {"result": ...}
        return dados.get("result", dados) if set(dados) == {"result"} else dados
    try:
        return json.loads(texto)
    except json.JSONDecodeError as erro:
        raise ErroMCP(f"retorno de {ferramenta} não é JSON: {texto[:200]}") from erro


def chamar(ferramenta: str, **argumentos) -> dict:
    try:
        return asyncio.run(_chamar(ferramenta, argumentos))
    except ErroMCP:
        raise
    except Exception as erro:  # transporte, 401, servidor fora do ar
        raise ErroMCP(f"falha ao chamar {ferramenta}: {erro}") from erro


def _data(valor) -> date | None:
    try:
        return date.fromisoformat(str(valor)[:10]) if valor else None
    except ValueError:
        return None


def _sessoes(dados: dict) -> int | None:
    """Esquema v1: sessoes_terapia_ano (número). v2: sessoes_terapia.ano_corrente."""
    if isinstance(dados.get("sessoes_terapia_ano"), (int, float)):
        return int(dados["sessoes_terapia_ano"])
    s = dados.get("sessoes_terapia")
    if isinstance(s, dict) and isinstance(s.get("ano_corrente"), (int, float)):
        return int(s["ano_corrente"])
    if isinstance(s, (int, float)):
        return int(s)
    return None


@traceable(name="mcp.consultar_beneficiario", run_type="tool")
def consultar_beneficiario(carteirinha: str) -> Beneficiario:
    d = chamar("consultar_beneficiario", carteirinha=carteirinha)
    return Beneficiario(carteirinha=str(d.get("carteirinha") or carteirinha), nome=d.get("nome"),
                        plano=d.get("plano"),
                        data_adesao=_data(d.get("data_adesao")), status=d.get("status"),
                        sessoes_terapia_ano=_sessoes(d), cpf_mascarado=d.get("cpf_mascarado") or d.get("cpf"),
                        bruto=d)


@traceable(name="mcp.consultar_historico", run_type="tool")
def consultar_historico(carteirinha: str) -> Historico:
    d = chamar("consultar_historico", carteirinha=carteirinha)
    pedidos = d.get("pedidos") if isinstance(d, dict) else d
    saida = []
    for p in pedidos or []:
        if not isinstance(p, dict):
            continue
        valor = next((p[k] for k in ("valor_reembolsado_brl", "valor_reembolso_brl", "valor_reembolsado",
                                     "valor_reembolso", "valor") if p.get(k) is not None), 0)
        saida.append(PedidoAnterior(data=_data(p.get("data_atendimento") or p.get("data")),
                                    categoria=p.get("categoria") or p.get("categoria_documento"),
                                    valor_reembolsado=Decimal(str(valor)),
                                    protocolo=str(p["protocolo"]) if p.get("protocolo") else None,
                                    decisao=p.get("decisao"), bruto=p))
    return Historico(carteirinha=carteirinha, pedidos=saida)


@traceable(name="mcp.abrir_protocolo", run_type="tool")
def abrir_protocolo(carteirinha: str, payload: dict) -> str:
    d = chamar("abrir_protocolo", carteirinha=carteirinha, payload=payload)
    return str(d.get("protocolo") or d.get("numero") or "")

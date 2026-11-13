"""Nível 3 do mapa de blocos: os nós dos subagentes, com o bloco de baixo já conferido.

  * ag_triagem: com o MCP de verdade, cada uma das 17 personas é identificada pela carteirinha da
    mensagem; a carteirinha mascarada, a ausente e a inexistente deixam o pedido aguardando o cliente;
    o cliente já identificado não é consultado de novo. Pula se o servidor MCP estiver fora do ar.
  * ag_documento: a leitura (`analisar`, avaliada no nível 2) entra pronta; aqui se confere o que o nó
    faz com ela: situação de cada anexo, substituição do recibo corrigido e o pedido que segue ou aguarda.
"""

import json
import re
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents import documento, triagem
from tests.test_nivel1 import mcp

RAIZ = Path(__file__).resolve().parents[1]
PERSONAS = sorted((RAIZ / "casos" / "treino").glob("*/persona.json"))


def _estado(msg, agente, pedido, **extra):
    chamada = AIMessage("", tool_calls=[{"name": agente, "args": {"pedido_id": pedido["id"]}, "id": "c1"}])
    return {"mensagens": [HumanMessage(msg), chamada], "pedidos": [pedido], **extra}


def _pedido(tipo, pid="1.1"):
    return {"id": pid, "tipo": tipo, "descricao": "x", "situacao": "pendente", "na_rodada": True}


# ------------------------------------------------------------------ ag_triagem
@mcp
@pytest.mark.parametrize("arquivo", PERSONAS, ids=lambda p: p.parent.name[:2])
def test_triagem_identifica_cada_persona(arquivo):
    p = json.loads(arquivo.read_text(encoding="utf-8"))
    out = triagem.ag_triagem(_estado(f"Minha carteirinha é {p['carteirinha']}.", "ag_triagem", _pedido("dados_cadastro")))
    b = out["beneficiario"]
    assert (b["plano"], b["data_adesao"], b["status"]) == (p["plano"], p["data_adesao"], p["status"])
    assert b["carteirinha"] == re.sub(r"\D", "", p["carteirinha"])
    assert out["pedidos"][0]["situacao"] == "atendido"


@mcp
@pytest.mark.parametrize("msg, motivo", [
    ("Minha carteirinha é 7042 0000 0000 0000.", "não foi localizada"),
    ("Meu pai fez um exame. A carteirinha dele é [carteirinha de outra pessoa].", "informar o número"),
    ("Quero pedir reembolso de uma consulta.", "informar o número"),
])
def test_triagem_sem_carteirinha_valida_aguarda_o_cliente(msg, motivo):
    out = triagem.ag_triagem(_estado(msg, "ag_triagem", _pedido("reembolso")))
    p = out["pedidos"][0]
    assert "beneficiario" not in out and p["situacao"] == "aguardando_cliente" and motivo in p["motivo"]


def test_triagem_com_cliente_ja_identificado_nao_consulta_de_novo(monkeypatch):
    monkeypatch.setattr(triagem, "_consultar", lambda c: pytest.fail("consultou o MCP de novo"))
    out = triagem.ag_triagem(_estado("A carteirinha da minha esposa é 7042 9999 8888 7777.", "ag_triagem",
                                     _pedido("reembolso"), beneficiario={"plano": "Pleno", "carteirinha": "1"}))
    assert "beneficiario" not in out and out["pedidos"][0]["situacao"] == "pendente"


# ------------------------------------------------------------------ ag_normas
def test_reembolso_ja_decidido_sem_mudanca_nao_e_decidido_de_novo(monkeypatch):
    from app.agents import normas
    from app.agents.estado import assinatura

    monkeypatch.setattr(normas, "decidir", lambda *a, **k: pytest.fail("decidiu de novo"))
    docs = [{"id": "anexo_01", "situacao": "ativo", "molde": {"classificacao": "SESSAO_TERAPIA"}}]
    base = {"documentos": docs, "beneficiario": {"plano": "Pleno", "carteirinha": "1"}}
    p = {**_pedido("reembolso"), "resultado": {"decisao": "PENDENTE_DOCUMENTO"}, "assinatura": assinatura(base)}
    out = normas.ag_normas({**_estado("Tem prazo pra levar o relatório?", "ag_normas", p), **base})
    assert out["pedidos"][0]["situacao"] == "aguardando_cliente" and "registre-a" in out["mensagens"][0].content


def test_situacao_de_pedido_anterior_sem_carteirinha_aguarda_o_cliente(monkeypatch):
    from app.agents import normas

    monkeypatch.setattr(normas, "consultar_historico", lambda c: pytest.fail("consultou sem o cliente identificado"))
    out = normas.ag_normas(_estado("o pedido de abril já saiu?", "ag_normas", _pedido("status_pedido")))
    p = out["pedidos"][0]
    assert p["situacao"] == "aguardando_cliente" and p["motivo"] == "informar o número da carteirinha"


def test_situacao_de_pedido_anterior_vem_do_historico(monkeypatch):
    from datetime import date
    from decimal import Decimal

    from app import tools
    from app.agents import normas

    anterior = tools.PedidoAnterior(data=date(2026, 3, 2), categoria="EXAME_DIAGNOSTICO", protocolo="20260000099",
                                    decisao="APROVADO", valor_reembolsado=Decimal("80.5"))
    monkeypatch.setattr(normas, "consultar_historico", lambda c: tools.Historico(carteirinha=c, pedidos=[anterior]))
    monkeypatch.setattr(normas, "norma_da_duvida_no_atendimento", lambda e, d: "norma")
    out = normas.ag_normas(_estado("o pedido de março já saiu?", "ag_normas", _pedido("status_pedido"),
                                   beneficiario={"plano": "Pleno", "carteirinha": "1"}))
    p = out["pedidos"][0]
    assert p["situacao"] == "atendido" and p["resultado"]["norma"].startswith("norma")
    assert "Citar: ART-81" in p["resultado"]["norma"] and "Citar: ART-15" in p["resultado"]["norma"]
    assert p["resultado"]["historico"] == [{"protocolo": "20260000099", "data_atendimento": "2026-03-02",
                                            "categoria": "EXAME_DIAGNOSTICO", "decisao": "APROVADO",
                                            "valor_reembolsado": "80.5"}]


def test_pergunta_que_esperava_a_carteirinha_volta_a_pendente_com_ela(monkeypatch):
    monkeypatch.setattr(triagem, "_consultar", lambda c: {"plano": "Pleno", "status": "ATIVO", "carteirinha": c})
    esperando = {**_pedido("status_pedido", "1.1"), "situacao": "aguardando_cliente",
                 "motivo": "informar o número da carteirinha", "na_rodada": False}
    reembolso = {**_pedido("reembolso", "1.2"), "situacao": "aguardando_cliente",
                 "motivo": "informar o número da carteirinha"}
    chamada = AIMessage("", tool_calls=[{"name": "ag_triagem", "args": {}, "id": "c1"}])
    out = triagem.ag_triagem({"mensagens": [HumanMessage("7042 8813 5561 0029"), chamada],
                              "pedidos": [esperando, reembolso]})
    status, reemb = out["pedidos"]
    assert status["situacao"] == "pendente" and status["na_rodada"] and not status["motivo"]
    assert reemb["situacao"] == "aguardando_cliente"   # o reembolso se retoma pelo registro do supervisor


# ------------------------------------------------------------------ ag_documento
def _lido(classificacao, fiscal=True, conselho="CRM-SP 1", data="2026-05-01", hash_="h1", descricao=""):
    """O que `analisar` devolveria; a situação é calculada pelo `situar` de verdade."""
    molde = documento.invalido("x", descricao) if classificacao == "INVALIDO" else {
        "classificacao": classificacao, "documento_fiscal": fiscal, "c3_registro_conselho": conselho,
        "c4_data_atendimento": data}

    def analisar(anexo, rodada, documentos, nome):
        novo = {"id": f"anexo_{len(documentos) + 1:02d}", "rodada": rodada, "arquivo": anexo["filename"],
                "leitura": "pdf", "hash": hash_, "molde": molde}
        novo["situacao"] = documento.situar(novo, documentos)
        return novo
    return analisar


def _doc(monkeypatch, lido, tipo="reembolso", documentos=()):
    monkeypatch.setattr(documento, "analisar", lido)
    out = documento.ag_documento(_estado("Segue o recibo.", "ag_documento", _pedido(tipo),
                                         anexo={"filename": "a.pdf"}, documentos=[dict(d) for d in documentos]))
    return out, out["pedidos"][0]


def test_recibo_valido_segue_para_a_decisao(monkeypatch):
    out, p = _doc(monkeypatch, _lido("CONSULTA_MEDICA"))
    assert out["documentos"][-1]["situacao"] == "ativo" and out["anexo"] is None and p["situacao"] == "pendente"


def test_arquivo_invalido_faz_o_reembolso_aguardar(monkeypatch):
    out, p = _doc(monkeypatch, _lido("INVALIDO", descricao="conta de luz"))
    assert out["documentos"][-1]["situacao"] == "invalido"
    assert p["situacao"] == "aguardando_cliente" and "conta de luz" in p["motivo"]


def test_documento_de_outra_pessoa_nao_e_processado_neste_atendimento(monkeypatch):
    def lido(anexo, rodada, documentos, nome):
        novo = {"id": "anexo_01", "rodada": rodada, "arquivo": anexo["filename"], "leitura": "pdf", "hash": "h1",
                "molde": documento.de_terceiro("anexo_01", "CONSULTA_MEDICA")}
        novo["situacao"] = documento.situar(novo, documentos)
        return novo
    out, p = _doc(monkeypatch, lido)
    m = out["documentos"][-1]["molde"]
    assert out["documentos"][-1]["situacao"] == "de_outra_pessoa" and m["classificacao"] == "CONSULTA_MEDICA"
    assert "c1_beneficiario_nome" not in m   # nenhum dado da outra pessoa fica no estado
    assert p["situacao"] == "aguardando_cliente" and "art. 8º" in p["motivo"]


def test_mesmo_arquivo_de_novo_e_duplicado(monkeypatch):
    anterior = {"id": "anexo_01", "hash": "h1", "situacao": "ativo", "molde": {"classificacao": "CONSULTA_MEDICA"}}
    out, p = _doc(monkeypatch, _lido("CONSULTA_MEDICA"), documentos=[anterior])
    assert out["documentos"][-1]["situacao"] == "duplicado" and p["situacao"] == "aguardando_cliente"


def test_recibo_corrigido_substitui_o_anterior(monkeypatch):
    anterior = {"id": "anexo_01", "hash": "h0", "situacao": "ativo",
                "molde": {"classificacao": "CONSULTA_MEDICA", "c3_registro_conselho": "CRM-SP 1",
                          "c4_data_atendimento": "2026-05-01"}}
    out, _ = _doc(monkeypatch, _lido("CONSULTA_MEDICA", hash_="h2"), documentos=[anterior])
    assert [d["situacao"] for d in out["documentos"]] == ["substituido", "ativo"]


def test_relatorio_sem_valor_e_complementar(monkeypatch):
    out, p = _doc(monkeypatch, _lido("RELATORIO_CLINICO", fiscal=False))
    assert out["documentos"][-1]["situacao"] == "complementar" and p["situacao"] == "pendente"


def test_documento_sem_pedido_de_reembolso_pergunta_o_que_fazer(monkeypatch):
    monkeypatch.setattr(documento, "analisar", _lido("CONSULTA_MEDICA"))
    out = documento.ag_documento(_estado("Enviei um arquivo, sem escrever nada.", "ag_documento", _pedido("documento"),
                                         anexo={"filename": "a.pdf"}, documentos=[]))
    p = out["pedidos"][0]
    assert p["situacao"] == "atendido" and "perguntar" in p["motivo"]


def test_recibo_enviado_com_mensagem_vira_reembolso(monkeypatch):
    _, p = _doc(monkeypatch, _lido("CONSULTA_MEDICA"), tipo="duvida_regra")
    assert p["tipo"] == "reembolso" and p["situacao"] == "pendente"


def test_relatorio_que_chega_com_uma_pergunta_completa_o_reembolso(monkeypatch):
    reembolso = {**_pedido("reembolso"), "id": "1.1", "situacao": "atendido"}
    duvida = {**_pedido("duvida_regra"), "id": "3.1"}
    monkeypatch.setattr(documento, "analisar", _lido("RELATORIO_CLINICO", fiscal=False))
    estado = _estado("Tenho o relatório, serve?", "ag_documento", duvida, anexo={"filename": "r.pdf"}, documentos=[])
    estado["pedidos"] = [reembolso, duvida]
    out = documento.ag_documento(estado)
    r = next(p for p in out["pedidos"] if p["id"] == "1.1")
    assert r["situacao"] == "pendente" and "completa o reembolso 1.1" in out["mensagens"][0].content

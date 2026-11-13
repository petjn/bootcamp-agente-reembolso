"""Código que depende de algo de fora (servidor MCP, arquivos PDF), sem modelo de linguagem.

  * MCP: para cada uma das 17 personas, o cadastro e o histórico que o servidor devolve batem com o
    persona.json do caso. Precisa do servidor MCP no ar (pula se não estiver).
  * Leitura dos anexos: cada PDF devolve o texto com o valor, a data e o código TUSS que estão nele.
"""

import base64
import json
import re
from pathlib import Path

import pytest

from app import tools
from app.agents.documento import ler_texto

RAIZ = Path(__file__).resolve().parents[1]
PERSONAS = sorted((RAIZ / "casos" / "treino").glob("*/persona.json"))


def _mcp_no_ar() -> bool:
    try:
        tools.consultar_beneficiario("0000000000000000")
    except tools.ErroMCP as e:
        return "não localizado" in str(e)
    except Exception:  # noqa: BLE001
        return False
    return True


mcp = pytest.mark.skipif(not _mcp_no_ar(), reason="servidor MCP fora do ar")


@mcp
@pytest.mark.parametrize("arquivo", PERSONAS, ids=lambda p: p.parent.name[:2])
def test_cadastro_e_historico_de_cada_persona(arquivo):
    p = json.loads(arquivo.read_text(encoding="utf-8"))
    numero = re.sub(r"\D", "", p["carteirinha"])
    b = tools.consultar_beneficiario(numero)
    assert (b.plano, str(b.data_adesao), b.status) == (p["plano"], p["data_adesao"], p["status"])
    h = tools.consultar_historico(numero)
    # sem a lista na persona, o servidor monta o histórico a partir do total reembolsado no ano
    if "historico" in p:
        assert len(h.pedidos) == len(p["historico"])
    assert sum(float(x.valor_reembolsado) for x in h.pedidos) == pytest.approx(p.get("reembolsado_no_ano_brl", 0), abs=0.01)


@mcp
def test_carteirinha_inexistente():
    with pytest.raises(tools.ErroMCP, match="não localizado"):
        tools.consultar_beneficiario("7042000000000000")


ANEXOS = sorted(p for grupo in ("treino", "ramos", "teste") for p in (RAIZ / "casos" / grupo).glob("*/*.pdf"))


@pytest.mark.parametrize("arquivo", ANEXOS, ids=lambda p: p.stem)
def test_leitura_do_anexo(arquivo):
    texto, metodo = ler_texto({"filename": arquivo.name, "mime_type": "application/pdf",
                               "base64": base64.b64encode(arquivo.read_bytes()).decode()})
    assert metodo == "pdf" and len(texto) > 100
    # recibos e notas trazem valor e data; o relatório clínico traz o profissional e o registro dele (há relatório
    # sem a indicação de manutenção de propósito, caso 37)
    if "relatorio" in arquivo.stem and "recibo" not in arquivo.stem:
        assert re.search(r"CR[MP]|CREFITO", texto)
    elif arquivo.stem.startswith("pedido_medico"):   # o pedido médico não tem valor: traz o exame e a data da solicitação
        assert re.search(r"(?i)solicita", texto)
    else:   # recibo do exterior traz o valor em outra moeda (art. 69)
        assert re.search(r"R\$ ?\d|EUR ?\d", texto)
    if ("recibo" in arquivo.stem or "nota" in arquivo.stem) and "sem_data" not in arquivo.stem:   # sem data de propósito
        assert re.search(r"\d{2}/\d{2}/\d{4}", texto)

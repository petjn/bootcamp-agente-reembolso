"""Eval do nó ag_normas (nível 3): o reembolso de cada caso de treino decidido com tudo de verdade
menos a leitura do documento.

    python -m scripts.eval_normas [casos]

O molde entra pronto e conferido à mão (o mesmo de tests/test_decisao_casos.py; a leitura tem eval
próprio, no nível 2). O resto é real: cadastro e histórico do MCP, julgamento do Anexo IV pelo modelo,
protocolo aberto no MCP. A data de hoje é a da conversa do caso. Confere decisão, valor, regras
essenciais e protocolo, como o avaliador.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.normas import ag_normas
from app.agents.triagem import _consultar
from tests.test_decisao_casos import DOCUMENTOS, _molde

CASOS = Path(__file__).resolve().parents[1] / "casos" / "treino"


def rodar(caso: str) -> list[str]:
    pasta = next(CASOS.glob(f"{caso}_*"))
    persona = json.loads((pasta / "persona.json").read_text(encoding="utf-8"))
    esperado = json.loads((pasta / "esperado.json").read_text(encoding="utf-8"))
    os.environ["DATA_REFERENCIA"] = esperado["_data_da_conversa"]
    categoria, data, tuss, valor, complementares = DOCUMENTOS[caso]
    docs = [{"id": "anexo_01", "arquivo": "recibo.pdf", "situacao": "ativo", "molde": _molde(categoria, data, tuss, valor)}]
    docs += [{"id": f"anexo_0{i + 2}", "situacao": "complementar", **c} for i, c in enumerate(complementares)]
    pedido = {"id": "1.1", "tipo": "reembolso", "descricao": "reembolso do atendimento", "situacao": "pendente",
              "na_rodada": True}
    chamada = AIMessage("", tool_calls=[{"name": "ag_normas", "args": {"pedido_id": "1.1"}, "id": "c1"}])
    estado = {"mensagens": [HumanMessage("Quero o reembolso."), chamada], "pedidos": [pedido], "documentos": docs,
              "beneficiario": _consultar(re.sub(r"\D", "", persona["carteirinha"]))}
    r = ag_normas(estado)["pedidos"][0]["resultado"]
    erros = []
    if r["decisao"] != esperado["decisao"]:
        erros.append(f"decisão {r['decisao']} ({r['motivo']})")
    if esperado["decisao"] in ("APROVADO", "APROVADO_PARCIAL") and abs((r["valor_reembolso"] or 0)
                                                                     - esperado["valor_reembolso_brl"]) > 0.01:
        erros.append(f"valor {r['valor_reembolso']}")
    if faltam := set(esperado["regras_aplicadas"]) - set(r["regras"]):
        erros.append(f"faltam regras {sorted(faltam)}")
    if bool(esperado.get("protocolo")) != bool(r["protocolo"]):
        erros.append(f"protocolo {r['protocolo']}")
    return erros


def main(so: list[str] | None = None) -> None:
    acertos = 0
    casos = [c for c in sorted(DOCUMENTOS) if not so or c in so]
    for caso in casos:
        erros = rodar(caso)
        acertos += not erros
        print(f"{'ok ' if not erros else 'ERR'} caso {caso}{': ' + '; '.join(erros) if erros else ''}", flush=True)
    print(f"\nTOTAL: {acertos}/{len(casos)}")


if __name__ == "__main__":
    main(sys.argv[1].split(",") if len(sys.argv) > 1 else None)

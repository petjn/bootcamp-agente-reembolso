"""Eval do julgamento do Anexo IV (a lista do que o plano não cobre): procedimento excluído, de fronteira ou coberto.

    python -m scripts.eval_anexo_iv [repeticoes]

Chama `decisao.julgar_anexo_iv` (busca dos itens + modelo) com procedimentos de cada grupo do Anexo IV e
procedimentos comuns, e confere o desfecho que a decisão usa:
  "excluido"   excluído de plano (indeferido sem apuração);
  "falta_indicacao"  grupo 3 sem indicação clínica (pendência pedindo a indicação);
  "coberto"    não é exclusão (segue para o cálculo).
"""

from __future__ import annotations

import sys
from datetime import date

from app.decisao import julgar_anexo_iv

DIA = date(2026, 5, 20)

# (procedimento, categoria, indicação clínica no documento, desfecho esperado)
ITENS = [
    ("Sessão de acupuntura", "SESSAO_TERAPIA", False, "falta_indicacao"),
    ("Sessão de acupuntura", "SESSAO_TERAPIA", True, "coberto"),
    ("Drenagem linfática manual", "SESSAO_TERAPIA", False, "falta_indicacao"),
    ("Sessão de pilates", "SESSAO_TERAPIA", False, "falta_indicacao"),
    ("Aplicação de toxina botulínica com finalidade estética", "CONSULTA_MEDICA", False, "excluido"),
    ("Lipoaspiração de abdome", "CONSULTA_MEDICA", False, "excluido"),
    ("Sessão de ozonioterapia", "SESSAO_TERAPIA", False, "excluido"),
    ("Clareamento dental", "CONSULTA_MEDICA", False, "excluido"),
    ("Consulta médica em consultório — dermatologia", "CONSULTA_MEDICA", False, "coberto"),
    ("Sessão de psicoterapia individual", "SESSAO_TERAPIA", False, "coberto"),
    ("Dosagem de hormônio tireoestimulante (TSH)", "EXAME_DIAGNOSTICO", False, "coberto"),
    ("Sessão de fisioterapia motora", "SESSAO_TERAPIA", False, "coberto"),
    # atendimento e despesa do grupo 5 num item só: o julgamento acha o item do grupo 5, e a decisão, vendo também
    # o código do procedimento, pede a discriminação (art. 59, § 2º; D80)
    ("Consulta médica e taxa administrativa", "CONSULTA_MEDICA", False, "excluido"),
    # como vem no recibo do caso 08 (sem acento), com o código TUSS achado na tabela
    ("Sessao de acupuntura", "SESSAO_TERAPIA", False, "falta_indicacao"),
]
CODIGOS = {"Sessao de acupuntura": "TUSS-50000646"}


def desfecho(j) -> str:
    return j.desfecho if j else "coberto"


def main(repeticoes: int = 2) -> None:
    acertos = total = 0
    for procedimento, categoria, indicacao, esperado in ITENS:
        molde = {"classificacao": categoria, "c10_indicacao_clinica": indicacao,
                 "c5_itens": [{"descricao": procedimento, "codigo_tuss": CODIGOS.get(procedimento)}]}
        for _ in range(repeticoes):
            j = julgar_anexo_iv(molde, DIA)
            obtido = desfecho(j)
            acertos += obtido == esperado
            total += 1
            detalhe = f"item {j.item}, {j.motivo}" if j else "sem itens do Anexo IV na busca"
            print(f"{'ok ' if obtido == esperado else 'ERR'} {procedimento} (indicação: {indicacao}): "
                  f"{obtido}, esperado {esperado} | {detalhe}", flush=True)
    print(f"\nTOTAL: {acertos}/{total} ({100 * acertos / total:.0f}%)")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2)

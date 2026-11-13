"""A data de "hoje" do agente.

O prazo para pedir reembolso (art. 12) conta da data do atendimento até a data do
pedido, que é o dia da conversa. Os casos de treino foram escritos para uma data fixa
(`_data_da_conversa` no esperado.json); rodando em outra data, um atendimento que
estava no prazo naquele dia pode cair fora dele.

`DATA_REFERENCIA` no ambiente (AAAA-MM-DD) fixa esse dia para testes e para o
motor de avaliação. Sem ela, vale a data real.
"""

from __future__ import annotations

import os
from datetime import date

from app.llm import carregar_env


def hoje() -> date:
    carregar_env()
    valor = os.getenv("DATA_REFERENCIA", "").strip()
    return date.fromisoformat(valor) if valor else date.today()

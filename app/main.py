"""API do agente. As 3 rotas são obrigatórias; o miolo é seu.

    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import json
import os

from fastapi import FastAPI

from app.llm import carregar_env
from app.schemas import ChatRequest, ChatResponse

# Lê o `.env` no start. O que já vem do ambiente vence: assim, quem roda o
# container pode passar as próprias credenciais no `docker run`.
carregar_env()

app = FastAPI(title="Agente de Reembolso")


@app.get("/health")
def health() -> dict:
    """Precisa responder 200 em até 60 segundos do start do container.

    Não construa índice aqui: o `storage/` já vem pronto na imagem.
    """
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """Um turno de conversa.

    O avaliador NÃO reenvia o histórico: recupere o estado da conversa pelo
    `session_id`, com o checkpointer do seu grafo.
    """
    from app.agents.grafo import turno

    resposta = turno(req.session_id, req.mensagem, req.anexo.model_dump() if req.anexo else None)
    if destino := os.getenv("LOG_CONVERSAS"):   # depuração: cada turno inteiro, numa linha JSON
        with open(destino, "a", encoding="utf-8") as f:
            f.write(json.dumps({"session_id": req.session_id, "mensagem": req.mensagem,
                                "anexo": req.anexo.filename if req.anexo else None,
                                **resposta.model_dump(mode="json")}, ensure_ascii=False) + "\n")
    return resposta


@app.post("/reset")
def reset() -> dict:
    """Limpa estado e sessões. Chamado entre conversas."""
    from app.agents.grafo import reset as limpar

    limpar()
    return {"status": "ok"}

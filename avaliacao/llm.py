"""Cliente do endpoint de LLM da banca — Gemini, pela porta nativa.

ADAPTADO no projeto de portfólio: sem o gateway, usa o Ollama local (ver
`_usar_ollama`). O resto do motor de avaliação não foi alterado.

Usa as mesmas duas variáveis que você configura no `.env`, e o mesmo modelo que
responde ao seu agente. `temperature=0`: a nota tem de ser a mesma se a correção
for repetida.

    BOOTCAMP_LLM_ENDPOINT=https://...        (sem /v1beta no fim)
    BOOTCAMP_API_KEY=bc26_...

Fala direto com `POST /v1beta/models/{modelo}:generateContent`, que é o formato
do Gemini. Se você preferir montar o seu agente com outra biblioteca, tudo bem —
o endpoint também aceita o formato da OpenAI, no `/v1`. As duas portas consomem
o mesmo crédito.
"""

from __future__ import annotations

import json
import os
import re

import httpx

TIMEOUT = 120.0
TENTATIVAS = 3


class LLMIndisponivel(RuntimeError):
    pass


def _config() -> tuple[str, str, str]:
    endpoint = os.getenv("BOOTCAMP_LLM_ENDPOINT", "").rstrip("/")
    chave = os.getenv("BOOTCAMP_API_KEY", "")
    # O gateway impõe o modelo da prova; este campo existe para o log e para
    # quem corrigir apontando para outro endpoint.
    modelo = os.getenv("BOOTCAMP_JUIZ_MODELO", "gemini-2.5-flash-lite")
    if not endpoint or not chave:
        raise LLMIndisponivel(
            "defina BOOTCAMP_LLM_ENDPOINT e BOOTCAMP_API_KEY para usar o juiz")
    # Aceita endpoint com ou sem /v1 no fim: o candidato pode ter copiado de um
    # exemplo do formato OpenAI, e não é por isso que a correção vai falhar.
    endpoint = re.sub(r"/v1(beta)?$", "", endpoint)
    return endpoint, chave, modelo


def _extrair_json(texto: str) -> dict:
    """O modelo às vezes embrulha o JSON em cerca de código."""
    texto = texto.strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto, flags=re.S)
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        inicio, fim = texto.find("{"), texto.rfind("}")
        if inicio >= 0 and fim > inicio:
            return json.loads(texto[inicio:fim + 1])
        raise


def _texto_da_resposta(devolvido: dict) -> str:
    for candidato in devolvido.get("candidates") or []:
        partes = (candidato.get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in partes if isinstance(p, dict))
    return ""


def _usar_ollama() -> bool:
    """Projeto de portfólio: sem o gateway da banca, o beneficiário simulado e o juiz
    rodam no mesmo modelo local do agente, pelo Ollama (como no original, as duas
    pontas usam o mesmo modelo que responde ao agente). Força com
    BOOTCAMP_JUIZ_BACKEND=ollama; sem as variáveis do gateway, é o padrão."""
    if os.getenv("BOOTCAMP_JUIZ_BACKEND", "").lower() == "ollama":
        return True
    return not (os.getenv("BOOTCAMP_LLM_ENDPOINT") and os.getenv("BOOTCAMP_API_KEY"))


def _perguntar_ollama(sistema: str, usuario: str) -> dict:
    url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    modelo = os.getenv("BOOTCAMP_JUIZ_MODELO_LOCAL") or os.getenv("MODELO_CHAT") or "gemma4:e4b-it-qat"
    # BOOTCAMP_JUIZ_PENSAR=1 liga o thinking do juiz local (para comparar juízes)
    pensar = os.getenv("BOOTCAMP_JUIZ_PENSAR", "") in ("1", "true", "sim")
    corpo = {"model": modelo, "stream": False, "format": "json", "think": pensar, "keep_alive": 1800,
             "options": {"temperature": 0, "num_ctx": 16384},
             "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]}
    ultimo = None
    for tentativa in range(TENTATIVAS):
        try:
            with httpx.Client(timeout=TIMEOUT) as c:
                r = c.post(f"{url}/api/chat", json=corpo)
                r.raise_for_status()
                return _extrair_json(r.json()["message"]["content"])
        except (httpx.HTTPError, KeyError, json.JSONDecodeError) as erro:
            ultimo = erro
    raise LLMIndisponivel(f"o juiz não conseguiu resposta do modelo local: {ultimo}")


def perguntar_json(sistema: str, usuario: str) -> dict:
    """Uma chamada, resposta em JSON. Determinística por construção."""
    if _usar_ollama():
        return _perguntar_ollama(sistema, usuario)
    endpoint, chave, modelo = _config()
    url = f"{endpoint}/v1beta/models/{modelo}:generateContent"
    corpo = {
        "systemInstruction": {"parts": [{"text": sistema}]},
        "contents": [{"role": "user", "parts": [{"text": usuario}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    cabecalhos = {"x-goog-api-key": chave, "content-type": "application/json"}

    ultimo = None
    for tentativa in range(TENTATIVAS):
        try:
            with httpx.Client(timeout=TIMEOUT) as c:
                r = c.post(url, json=corpo, headers=cabecalhos)
                r.raise_for_status()
                return _extrair_json(_texto_da_resposta(r.json()))
        except (httpx.HTTPError, KeyError, json.JSONDecodeError) as erro:
            ultimo = erro
            if tentativa == TENTATIVAS - 1:
                break
    raise LLMIndisponivel(f"o juiz não conseguiu resposta do modelo: {ultimo}")


def disponivel() -> bool:
    if _usar_ollama():
        try:
            url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
            return httpx.get(f"{url}/api/version", timeout=5).status_code == 200
        except httpx.HTTPError:
            return False
    return bool(os.getenv("BOOTCAMP_LLM_ENDPOINT") and os.getenv("BOOTCAMP_API_KEY"))

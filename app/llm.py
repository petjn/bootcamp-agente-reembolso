"""Onde o modelo entra. Tudo local, servido pelo Ollama.

O projeto original usava Gemini 2.5 Flash Lite e gemini-embedding-2 por um
gateway do bootcamp. Aqui usamos a família aberta do Google, Gemma 4, rodando
na máquina (ver docs/diario_de_decisoes.md, D2, D2b e D11):

    chat        gemma4:e4b-it-qat       na GPU, inteiro (3,1 GB), sem thinking
    embeddings  embeddinggemma:300m     na CPU no atendimento, GPU no ingest
    reranker    bge-reranker-v2-m3      na GPU, ao lado do chat (app/rag)

    from app.llm import criar_llm, criar_embeddings
    llm = criar_llm()                        # LangChain / LangGraph
    emb = criar_embeddings()

    from app.llm import criar_embeddings_llamaindex
    Settings.embed_model = criar_embeddings_llamaindex()    # LlamaIndex (só embeddings)

Variáveis opcionais no `.env`: OLLAMA_BASE_URL, MODELO_CHAT, MODELO_EMBEDDING.
No ambiente: NUM_CTX, NUM_GPU, PENSAR_NOS e LOG_LLM (log local de cada chamada, D43).
"""

from __future__ import annotations

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

PADROES = {
    "OLLAMA_BASE_URL": "http://localhost:11434",
    # o 12b não cabe inteiro nos 8 GB; o e4b cabe e deixa espaço para o reranker (D11)
    "MODELO_CHAT": "gemma4:e4b-it-qat",
    # embeddinggemma-2 exige MLX (só Apple); no Windows usamos a versão 1.
    "MODELO_EMBEDDING": "embeddinggemma:300m",
}

# Mantém os modelos carregados entre turnos; recarregar custa segundos.
KEEP_ALIVE = 1800  # segundos

# Janela de contexto do chat: 24 mil tokens (D49). Com o quadro de mudanças e os artigos da decisão (D46),
# a maior chamada medida nas rodadas 22 e 23 passou a 15,6 mil de entrada (a resposta, com duas dúvidas);
# 24 mil mantém a folga de 50% da D40, que tinha fixado 16 mil sobre um máximo de 10,7 mil. Antes da D40 era
# 50 mil, o limite da avaliação original (D32).
NUM_CTX = int(os.getenv("NUM_CTX") or 24576)   # NUM_CTX no ambiente troca a janela (ex.: testes de modelo)


def carregar_env() -> None:
    """Lê o `.env` da raiz do repositório, sem depender de biblioteca.

    O que já está no ambiente vence o arquivo.
    """
    env = RAIZ / ".env"
    if not env.exists():
        return
    for linha in env.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def config(nome: str) -> str:
    carregar_env()
    return os.getenv(nome, "").strip() or PADROES[nome]


def _gpu(na_gpu: bool) -> dict:
    # num_gpu=0 força a CPU. Sem a chave, o Ollama decide (usa a GPU se couber).
    return {} if na_gpu else {"num_gpu": 0}


# ------------------------------------------------------- log local das chamadas
_LOG = {}


def _log_local():
    """LOG_LLM=caminho.jsonl grava cada chamada ao modelo de chat numa linha: nó do grafo, prompt,
    resposta, raciocínio (thinking), tokens e tempo. É o que o LangSmith mostrava, sem sair da máquina."""
    caminho = os.getenv("LOG_LLM", "").strip()
    if not caminho:
        return None
    if caminho not in _LOG:
        import json
        import threading
        import time

        from langchain_core.callbacks import BaseCallbackHandler

        trava = threading.Lock()

        def _msg(m) -> dict:
            d = {"tipo": m.type, "conteudo": m.content}
            for campo in ("name", "tool_calls"):
                if getattr(m, campo, None):
                    d[campo] = getattr(m, campo)
            return d

        class LogLocal(BaseCallbackHandler):
            def __init__(self):
                self.abertas = {}

            def on_chat_model_start(self, serialized, messages, *, run_id, metadata=None, **kw):
                self.abertas[run_id] = (time.time(), metadata or {}, [_msg(m) for m in messages[0]])

            def _gravar(self, run_id, **campos):
                inicio, meta, prompt = self.abertas.pop(run_id, (time.time(), {}, []))
                linha = {"quando": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(inicio)),
                         "segundos": round(time.time() - inicio, 1), "thread": meta.get("thread_id"),
                         "no": meta.get("langgraph_node"), "modelo": meta.get("ls_model_name"),
                         "prompt": prompt, **campos}
                Path(caminho).parent.mkdir(parents=True, exist_ok=True)
                with trava, open(caminho, "a", encoding="utf-8") as f:
                    f.write(json.dumps(linha, ensure_ascii=False, default=str) + "\n")

            def on_llm_end(self, response, *, run_id, **kw):
                m = getattr(response.generations[0][0], "message", None)
                self._gravar(run_id, resposta=getattr(m, "content", response.generations[0][0].text),
                             raciocinio=(getattr(m, "additional_kwargs", None) or {}).get("reasoning_content"),
                             tool_calls=getattr(m, "tool_calls", None), tokens=getattr(m, "usage_metadata", None))

            def on_llm_error(self, error, *, run_id, **kw):
                self._gravar(run_id, erro=repr(error))

        _LOG[caminho] = LogLocal()
    return _LOG[caminho]


# ------------------------------------------------------- LangChain / LangGraph
def criar_llm(**extra):
    """O modelo de chat, pronto para `bind_tools` e `with_structured_output`."""
    from langchain_ollama import ChatOllama

    # NUM_GPU (opcional): camadas na GPU. Sem ela, o Ollama decide e, com modelo grande, deixa parte na CPU
    # mesmo quando caberia inteiro; NUM_GPU=99 força tudo na placa (D42)
    if (n := os.getenv("NUM_GPU", "").strip()) and "num_gpu" not in extra:
        extra["num_gpu"] = int(n)
    if (log := _log_local()) and "callbacks" not in extra:
        extra["callbacks"] = [log]
    return ChatOllama(
        model=extra.pop("model", config("MODELO_CHAT")), base_url=config("OLLAMA_BASE_URL"),
        temperature=extra.pop("temperature", 0), keep_alive=KEEP_ALIVE,
        num_ctx=extra.pop("num_ctx", NUM_CTX),
        # thinking desligado, como o Gemini 2.5 Flash Lite original (D2e). Sem isto o
        # Gemma 4 pensa por padrão e cada chamada leva 10 a 20 s.
        reasoning=extra.pop("reasoning", False), **extra)


def pensar(no: str) -> bool:
    """Thinking ligado só nos nós listados em PENSAR_NOS (ex.: "supervisor,responder").
    Padrão: só no supervisor, como nas rodadas (D48, D50). O padrão antigo, "responder", fazia os testes refeitos fora
    do Studio rodarem a resposta com thinking, e o resultado deles não batia com o das rodadas (D90)."""
    return no in {n.strip() for n in os.getenv("PENSAR_NOS", "supervisor").split(",")}


def estruturado(schema, prompt, no: str = ""):
    """Saída Pydantic. Primeiro por chamada de ferramenta: com o esquema imposto na
    decodificação (json_schema) o Gemma deixa quase tudo nulo em moldes grandes. Se o
    modelo não chamar a ferramenta, chamar outra ou faltar campo obrigatório, tenta de novo pelo
    esquema."""
    from langchain_core.exceptions import OutputParserException
    from pydantic import ValidationError

    llm = criar_llm(reasoning=pensar(no))
    try:
        saida = llm.with_structured_output(schema, method="function_calling").invoke(prompt)
    except (ValidationError, OutputParserException):   # campo faltando ou ferramenta com outro nome
        saida = None
    return saida if saida is not None else llm.with_structured_output(schema).invoke(prompt)


def criar_embeddings(na_gpu: bool = False, **extra):
    """Embeddings. Por padrão na CPU, para não disputar a GPU com o chat."""
    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(
        model=config("MODELO_EMBEDDING"), base_url=config("OLLAMA_BASE_URL"),
        keep_alive=KEEP_ALIVE, **_gpu(na_gpu), **extra)


# ------------------------------------------------------------------ LlamaIndex
def criar_embeddings_llamaindex(na_gpu: bool = False, **extra):
    from llama_index.embeddings.ollama import OllamaEmbedding

    return OllamaEmbedding(model_name=config("MODELO_EMBEDDING"),
                           base_url=config("OLLAMA_BASE_URL"),
                           ollama_additional_kwargs=_gpu(na_gpu),
                           keep_alive=KEEP_ALIVE, **extra)


if __name__ == "__main__":
    # python -m app.llm  -> confere a configuração antes de começar
    import time

    t = time.perf_counter()
    print("chat      :", criar_llm().invoke("Responda apenas: pronto.").content.strip(),
          f"({time.perf_counter() - t:.1f}s)")
    t = time.perf_counter()
    print("embeddings:", len(criar_embeddings().embed_query("teste")), "dimensões",
          f"({time.perf_counter() - t:.1f}s)")

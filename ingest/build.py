"""Constrói tudo o que o agente consulta e grava em storage/.

    python -m ingest.build

Roda FORA do container, na sua máquina. Depois você commita `storage/` e o
Dockerfile só copia — o build da imagem precisa ser offline e determinístico, e
o `/health` tem 60 segundos para responder.

Etapas, todas sem internet (o Ollama é local):
  1. grafo normativo das circulares       storage/grafo_normativo.json
  2. Tabela URS por código                storage/tabela_urs.json
  3. parâmetros extraídos do texto        storage/parametros.json
  4. chunks com metadados (ingest/chunking.py)
  5. embeddings (EmbeddingGemma na GPU)   storage/indice/   (SimpleVectorStore)
  6. BM25 persistido                      storage/bm25/

Determinismo: o id de cada chunk vem do conteúdo, e o embedding de um chunk já
indexado é reaproveitado do índice anterior (mesmo id, mesmo modelo). Assim,
rodar o build de novo sem mudar a kb/ grava exatamente os mesmos bytes, e só
chunk novo ou alterado passa pelo modelo.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DIR_KB = RAIZ / "kb"
DIR_STORAGE = RAIZ / "storage"


def _embeddings_anteriores(modelo: str) -> dict[str, list[float]]:
    from app.rag import DIR_INDICE, MANIFESTO

    if not (MANIFESTO.exists() and (DIR_INDICE / "default__vector_store.json").exists()):
        return {}
    manifesto = json.loads(MANIFESTO.read_text(encoding="utf-8"))
    if manifesto.get("modelo_embedding") != modelo or manifesto.get("instrucao_documento") is None:
        return {}
    dados = json.loads((DIR_INDICE / "default__vector_store.json").read_text(encoding="utf-8"))
    return dados.get("embedding_dict", {})


def construir_indice(nos) -> dict:
    from llama_index.core import StorageContext, VectorStoreIndex
    from llama_index.core.schema import MetadataMode

    from app.llm import config
    from app.rag import (DIR_BM25, DIR_INDICE, ID_INDICE, INSTRUCAO_DOCUMENTO, MANIFESTO,
                         construir_bm25, criar_embeddings_busca)

    modelo = config("MODELO_EMBEDDING")
    # REEMBOLSO_RECALCULAR=1 ignora o índice anterior e recalcula todos os embeddings
    anteriores = {} if os.getenv("REEMBOLSO_RECALCULAR") == "1" else _embeddings_anteriores(modelo)
    faltam = [n for n in nos if n.id_ not in anteriores]
    print(f"   embeddings: {len(nos) - len(faltam)} reaproveitados, {len(faltam)} a calcular")
    if faltam:
        emb = criar_embeddings_busca(na_gpu=True)
        textos = [n.get_content(metadata_mode=MetadataMode.EMBED) for n in faltam]
        t = time.perf_counter()
        vetores = emb.get_text_embedding_batch(textos, show_progress=False)
        print(f"   {len(faltam)} embeddings em {time.perf_counter() - t:.0f}s")
        anteriores.update({n.id_: v for n, v in zip(faltam, vetores)})
    for n in nos:
        n.embedding = anteriores[n.id_]

    # Sem apagar as pastas: o OneDrive às vezes trava a remoção de diretório no Windows.
    # O persist sobrescreve os mesmos arquivos.
    contexto = StorageContext.from_defaults()
    indice = VectorStoreIndex(nos, storage_context=contexto, embed_model=criar_embeddings_busca())
    indice.set_index_id(ID_INDICE)
    contexto.persist(persist_dir=str(DIR_INDICE))

    construir_bm25(nos).persist(str(DIR_BM25))

    manifesto = {"modelo_embedding": modelo, "instrucao_documento": INSTRUCAO_DOCUMENTO,
                 "chunks": len(nos),
                 "por_arquivo": dict(sorted(_contar(nos).items())),
                 "kb_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted(DIR_KB.iterdir()) if p.is_file()}}
    MANIFESTO.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifesto


def _contar(nos) -> dict[str, int]:
    contagem: dict[str, int] = {}
    for n in nos:
        contagem[n.metadata["arquivo"]] = contagem.get(n.metadata["arquivo"], 0) + 1
    return contagem


def main() -> int:
    from ingest import chunking, grafo_normativo, parametros, tabela_urs

    t0 = time.perf_counter()
    print("1. grafo normativo");  grafo_normativo.main()
    print("2. Tabela URS");       tabela_urs.main()
    print("3. parâmetros");       parametros.main()
    grafo = json.loads((DIR_STORAGE / "grafo_normativo.json").read_text(encoding="utf-8"))
    tabela = json.loads((DIR_STORAGE / "tabela_urs.json").read_text(encoding="utf-8"))
    print("4. chunks")
    nos = chunking.todos(grafo, tabela)
    print(f"   {len(nos)} chunks")
    print("5-6. embeddings, índice vetorial e BM25")
    construir_indice(nos)
    print(f"pronto em {time.perf_counter() - t0:.0f}s -> storage/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import os
from datetime import datetime
from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings

FAISS_INDEX_DIR = os.getenv("CHROMA_PERSIST_DIR", "./faiss_index")
INDEX_FILE = "index"
_LOG_FILE = Path("./logs.txt")


def _log(msg: str):
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _LOG_FILE.open("a", encoding="utf-8").write(f"[{ts}] {msg}\n")
    except Exception:
        pass


# ── Embeddings ────────────────────────────────────────────────────────────────

_fastembed_model = None


def _get_fastembed_model():
    global _fastembed_model
    if _fastembed_model is None:
        from fastembed import TextEmbedding
        _fastembed_model = TextEmbedding("BAAI/bge-small-en-v1.5")
    return _fastembed_model


class _FastEmbedWrapper(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [e.tolist() for e in _get_fastembed_model().embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return list(_get_fastembed_model().embed([text]))[0].tolist()


_embeddings: _FastEmbedWrapper | None = None
_vectorstore: FAISS | None = None


def get_embeddings() -> _FastEmbedWrapper:
    global _embeddings
    if _embeddings is None:
        _embeddings = _FastEmbedWrapper()
        _embeddings.embed_query("warm up")
        _log("Embeddings loaded (BAAI/bge-small-en-v1.5)")
    return _embeddings


# ── Vector store ──────────────────────────────────────────────────────────────

def get_vectorstore() -> FAISS:
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore

    idx_path = Path(FAISS_INDEX_DIR)
    if (idx_path / f"{INDEX_FILE}.faiss").exists():
        _vectorstore = FAISS.load_local(
            str(idx_path), get_embeddings(), index_name=INDEX_FILE,
            allow_dangerous_deserialization=True,
        )
        _log(f"FAISS loaded from disk ({len(_vectorstore.docstore._dict)} vectors)")
    else:
        _vectorstore = FAISS.from_texts(
            ["Assistant initialized."],
            get_embeddings(),
            metadatas=[{"source": "__init__", "user_id": ""}],
        )
        _save()
        _log("FAISS created fresh (no index on disk)")

    return _vectorstore


def _save():
    Path(FAISS_INDEX_DIR).mkdir(parents=True, exist_ok=True)
    _vectorstore.save_local(FAISS_INDEX_DIR, index_name=INDEX_FILE)


def add_documents(docs, user_id: str = ""):
    for doc in docs:
        doc.metadata["user_id"] = user_id
    vs = get_vectorstore()
    vs.add_documents(docs)
    _save()
    _log(f"FAISS: added {len(docs)} chunks for user={user_id[:8]} (total={len(vs.docstore._dict)})")


def search_documents(query: str, user_id: str = "", k: int = 4) -> str:
    try:
        vs = get_vectorstore()
        total = len(vs.docstore._dict)
        fetch_k = min(max(total, 1), 40)
        candidates = vs.similarity_search(query, k=fetch_k)

        matches = [
            d for d in candidates
            if d.metadata.get("source") != "__init__"
            and (not user_id or d.metadata.get("user_id") == user_id)
        ]

        if not matches:
            _log(f"RAG: 0 matches for user={user_id[:8]} (index has {total} vectors)")
            return ""

        _log(f"RAG: {len(matches)} chunks retrieved for user={user_id[:8]}")
        return "\n\n---\n\n".join(
            f"[{d.metadata.get('source', 'unknown')}]\n{d.page_content}"
            for d in matches[:k]
        )
    except Exception as exc:
        _log(f"RAG ERROR in search_documents: {exc}")
        return ""


def delete_by_source(filename: str, user_id: str = ""):
    vs = get_vectorstore()
    ids_to_remove = [
        doc_id for doc_id, doc in vs.docstore._dict.items()
        if doc.metadata.get("source") == filename
        and (not user_id or doc.metadata.get("user_id") == user_id)
    ]
    if ids_to_remove:
        vs.delete(ids_to_remove)
        _save()


def reset_vectorstore():
    global _vectorstore
    _vectorstore = None

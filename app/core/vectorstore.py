import os
from datetime import datetime
from pathlib import Path

from langchain_core.embeddings import Embeddings
from supabase import create_client, Client

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


def get_embeddings() -> _FastEmbedWrapper:
    global _embeddings
    if _embeddings is None:
        _embeddings = _FastEmbedWrapper()
        _embeddings.embed_query("warm up")
        _log("Embeddings loaded (BAAI/bge-small-en-v1.5)")
    return _embeddings


# ── Vector store (Supabase / pgvector) ────────────────────────────────────────

TABLE = "document_chunks"
_supabase: Client | None = None


def get_vectorstore() -> Client:
    """Returns the Supabase client (kept as get_vectorstore for call-site compatibility)."""
    global _supabase
    if _supabase is None:
        url = os.getenv("SUPABASE_URL", "").strip()
        key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
        _supabase = create_client(url, key)
        _log("Supabase client initialised")
    return _supabase


def add_documents(docs, user_id: str = ""):
    client = get_vectorstore()
    embeddings = get_embeddings().embed_documents([d.page_content for d in docs])
    rows = [
        {
            "user_id": user_id,
            "source": doc.metadata.get("source", "unknown"),
            "content": doc.page_content,
            "embedding": embedding,
        }
        for doc, embedding in zip(docs, embeddings)
    ]
    client.table(TABLE).insert(rows).execute()
    _log(f"Supabase: added {len(rows)} chunks for user={user_id[:8]}")


def search_documents(query: str, user_id: str = "", k: int = 4) -> str:
    try:
        client = get_vectorstore()
        query_embedding = get_embeddings().embed_query(query)
        resp = client.rpc(
            "match_document_chunks",
            {
                "query_embedding": query_embedding,
                "match_user_id": user_id,
                "match_count": k,
            },
        ).execute()
        matches = resp.data or []

        if not matches:
            _log(f"RAG: 0 matches for user={user_id[:8]}")
            return ""

        _log(f"RAG: {len(matches)} chunks retrieved for user={user_id[:8]}")
        return "\n\n---\n\n".join(
            f"[{m.get('source', 'unknown')}]\n{m.get('content', '')}" for m in matches
        )
    except Exception as exc:
        _log(f"RAG ERROR in search_documents: {exc}")
        return ""


def delete_by_source(filename: str, user_id: str = ""):
    client = get_vectorstore()
    query = client.table(TABLE).delete().eq("source", filename)
    if user_id:
        query = query.eq("user_id", user_id)
    query.execute()
    _log(f"Supabase: deleted chunks for source={filename} user={user_id[:8]}")


def reset_vectorstore():
    global _supabase
    _supabase = None

import os
from pathlib import Path
from langchain_community.vectorstores import FAISS

FAISS_INDEX_DIR = os.getenv("CHROMA_PERSIST_DIR", "./faiss_index")
INDEX_FILE = "index"

_embeddings = None
_vectorstore: FAISS | None = None


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        _embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
        )
    return _embeddings


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
    else:
        # Bootstrap with a placeholder so FAISS has a valid index
        _vectorstore = FAISS.from_texts(
            ["Assistant initialized."],
            get_embeddings(),
            metadatas=[{"source": "__init__"}],
        )
        _save()

    return _vectorstore


def _save():
    Path(FAISS_INDEX_DIR).mkdir(parents=True, exist_ok=True)
    _vectorstore.save_local(FAISS_INDEX_DIR, index_name=INDEX_FILE)


def add_documents(docs):
    vs = get_vectorstore()
    vs.add_documents(docs)
    _save()


def delete_by_source(filename: str):
    """Remove all vectors whose metadata source matches filename."""
    global _vectorstore
    vs = get_vectorstore()
    all_data = vs.docstore._dict
    ids_to_remove = [
        doc_id for doc_id, doc in all_data.items()
        if doc.metadata.get("source") == filename
    ]
    if ids_to_remove:
        vs.delete(ids_to_remove)
        _save()


def list_sources() -> list[str]:
    vs = get_vectorstore()
    sources = {
        doc.metadata.get("source", "")
        for doc in vs.docstore._dict.values()
        if doc.metadata.get("source") not in ("", "__init__")
    }
    return sorted(sources)


def reset_vectorstore():
    global _vectorstore
    _vectorstore = None

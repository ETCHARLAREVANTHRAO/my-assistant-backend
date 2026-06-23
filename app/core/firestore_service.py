from firebase_admin import firestore as fb_firestore

LIMIT_BYTES = 15 * 1024 * 1024          # 15 MB per user
_MAX_TEXT_BYTES = 900_000                 # Stay under Firestore's 1 MB doc limit

_db = None


def get_db():
    global _db
    if _db is None:
        _db = fb_firestore.client()
    return _db


def get_user_size(user_id: str) -> int:
    docs = get_db().collection("users").document(user_id).collection("documents").stream()
    return sum(d.to_dict().get("size_bytes", 0) for d in docs)


def add_document(user_id: str, filename: str, size_bytes: int, chunks: int, text: str):
    get_db().collection("users").document(user_id).collection("documents").document(filename).set({
        "filename": filename,
        "size_bytes": size_bytes,
        "chunks": chunks,
        "text": text[:_MAX_TEXT_BYTES],
        "uploaded_at": fb_firestore.SERVER_TIMESTAMP,
    })


def list_documents(user_id: str) -> list[str]:
    docs = get_db().collection("users").document(user_id).collection("documents").stream()
    return sorted(d.id for d in docs)


def delete_document(user_id: str, filename: str):
    get_db().collection("users").document(user_id).collection("documents").document(filename).delete()


def get_all_documents() -> list[dict]:
    """Return every document across all users — used to rebuild FAISS on startup."""
    result = []
    try:
        for user_doc in get_db().collection("users").stream():
            uid = user_doc.id
            for doc in get_db().collection("users").document(uid).collection("documents").stream():
                d = doc.to_dict()
                d["user_id"] = uid
                result.append(d)
    except Exception:
        pass
    return result

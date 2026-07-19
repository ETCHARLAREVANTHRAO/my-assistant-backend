import os

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from app.models import DocumentUploadResponse, DocumentListResponse
from app.core.rag import ingest_document, delete_document, _log
from app.core.auth import verify_token, verify_admin_token
from app.core import firestore_service
from app.core import drive_sync

router = APIRouter(prefix="/documents", tags=["documents"])

SUPPORTED_EXTENSIONS = {"md", "txt", "pdf", "docx", "jpg", "jpeg", "png", "bmp", "tiff", "webp"}


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Depends(verify_token),
):
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    content_bytes = await file.read()
    if not content_bytes:
        raise HTTPException(status_code=400, detail="File is empty.")

    # Quota check
    used = firestore_service.get_user_size(user_id)
    limit = firestore_service.LIMIT_BYTES
    if used + len(content_bytes) > limit:
        used_mb = used / (1024 * 1024)
        limit_mb = limit / (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"Storage limit reached ({used_mb:.1f} MB used of {limit_mb:.0f} MB). "
                   "Contact admin to increase your limit.",
        )

    try:
        chunks, text = ingest_document(content_bytes, file.filename, user_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        import traceback
        _log(f"INGEST ERROR [{file.filename}]: {traceback.format_exc()}")
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")

    firestore_service.add_document(user_id, file.filename, len(content_bytes), chunks, text)

    return DocumentUploadResponse(
        filename=file.filename,
        chunks_stored=chunks,
        message=f"'{file.filename}' uploaded successfully ({chunks} chunks).",
    )


@router.get("", response_model=DocumentListResponse)
async def list_docs(user_id: str = Depends(verify_token)):
    docs = firestore_service.list_documents(user_id)
    used = firestore_service.get_user_size(user_id)
    return DocumentListResponse(
        documents=docs,
        used_bytes=used,
        limit_bytes=firestore_service.LIMIT_BYTES,
    )


@router.delete("/{filename}")
async def delete_doc(filename: str, user_id: str = Depends(verify_token)):
    delete_document(filename, user_id)
    firestore_service.delete_document(user_id, filename)
    return {"message": f"'{filename}' deleted."}


@router.post("/drive-sync")
async def drive_sync_endpoint(_admin_uid: str = Depends(verify_admin_token)):
    """Admin-only: sync the shared Drive folder into the global knowledge base
    used as background context for every user's chat — never a per-user document."""
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    if not folder_id:
        raise HTTPException(status_code=400, detail="GOOGLE_DRIVE_FOLDER_ID is not configured.")
    try:
        result = drive_sync.sync_folder(folder_id)
    except Exception as e:
        _log(f"DRIVE SYNC FAILED: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    return result

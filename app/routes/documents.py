from fastapi import APIRouter, UploadFile, File, HTTPException
from app.models import DocumentUploadResponse, DocumentListResponse
from app.core.rag import ingest_document, delete_document, list_documents, _log

router = APIRouter(prefix="/documents", tags=["documents"])

SUPPORTED_EXTENSIONS = {"md", "txt", "pdf", "docx", "jpg", "jpeg", "png", "bmp", "tiff", "webp"}


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    content_bytes = await file.read()
    if not content_bytes:
        raise HTTPException(status_code=400, detail="File is empty")

    try:
        chunks = ingest_document(content_bytes, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        import traceback
        detail = f"{type(e).__name__}: {e}"
        _log(f"INGEST ERROR [{file.filename}]: {traceback.format_exc()}")
        raise HTTPException(status_code=422, detail=detail)

    return DocumentUploadResponse(
        filename=file.filename,
        chunks_stored=chunks,
        message=f"Successfully ingested {chunks} chunks from '{file.filename}'",
    )


@router.get("", response_model=DocumentListResponse)
async def list_docs():
    docs = list_documents()
    return DocumentListResponse(documents=docs)


@router.delete("/{filename}")
async def delete_doc(filename: str):
    delete_document(filename)
    return {"message": f"Deleted '{filename}' from knowledge base"}

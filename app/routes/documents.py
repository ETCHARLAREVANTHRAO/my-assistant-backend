from fastapi import APIRouter, UploadFile, File, HTTPException
from app.models import DocumentUploadResponse, DocumentListResponse
from app.core.rag import ingest_markdown, delete_document, list_documents

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Only .md (Markdown) files are supported")

    content = (await file.read()).decode("utf-8")
    if not content.strip():
        raise HTTPException(status_code=400, detail="File is empty")

    chunks = ingest_markdown(content, file.filename)
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

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

from app.routes import chat, documents, weather


@asynccontextmanager
async def lifespan(_: FastAPI):
    from app.core.vectorstore import get_embeddings, get_vectorstore
    from app.core.rag import ingest_text
    from app.core import firestore_service

    get_embeddings()   # load ONNX model into memory
    get_vectorstore()  # initialise FAISS index

    # Rebuild FAISS from Firestore so documents survive Render restarts
    try:
        for doc in firestore_service.get_all_documents():
            if doc.get("text"):
                ingest_text(doc["text"], doc["filename"], doc["user_id"])
    except Exception:
        pass  # Firebase may not be ready in local dev without credentials

    yield


app = FastAPI(title="my_assistant API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://my-assistant-mobile.vercel.app",
        "http://localhost:8081",
        "http://localhost:19006",
        "http://localhost:3000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(weather.router)


@app.get("/health")
async def health():
    return {"status": "ok"}

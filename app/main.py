from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

from app.routes import chat, documents, weather


@asynccontextmanager
async def lifespan(_: FastAPI):
    from app.core.vectorstore import get_embeddings, get_vectorstore
    get_embeddings()   # load ONNX model into memory
    get_vectorstore()  # initialise FAISS index
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


@app.on_event("startup")
async def _preload():
    from app.core.vectorstore import get_embeddings, get_vectorstore
    get_embeddings()   # load ONNX model into memory
    get_vectorstore()  # initialise FAISS index


@app.get("/health")
async def health():
    return {"status": "ok"}

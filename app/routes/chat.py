from fastapi import APIRouter, HTTPException
from app.models import ChatRequest, ChatResponse
from app.core.rag import chat

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat_endpoint(body: ChatRequest):
    try:
        result = chat(body.message)
        return ChatResponse(reply=result["reply"], sources=result["sources"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

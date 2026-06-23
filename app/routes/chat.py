from fastapi import APIRouter, HTTPException, Depends
from app.models import ChatRequest, ChatResponse
from app.core.rag import chat
from app.core.auth import verify_token

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat_endpoint(body: ChatRequest, user_id: str = Depends(verify_token)):
    try:
        result = await chat(body.message, user_id)
        return ChatResponse(reply=result["reply"], sources=result["sources"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

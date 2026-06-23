from fastapi import APIRouter, HTTPException, Depends
from app.models import ChatRequest, ChatResponse
from app.core.rag import chat
from app.core.auth import verify_token
from app.core import usage_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat_endpoint(body: ChatRequest, user_id: str = Depends(verify_token)):
    usage_service.check_rate_limit(user_id)          # 5 msg / min  (in-memory)
    usage_service.check_and_increment_daily(user_id)  # 50 msg / day (Firestore)
    usage_service.check_monthly_limit(user_id)        # 100K tok/mo  (Firestore)

    try:
        result = await chat(body.message, user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Track tokens used (fire-and-forget — don't fail the response if this errors)
    try:
        if result.get("tokens_used"):
            usage_service.add_tokens(user_id, result["tokens_used"])
    except Exception:
        pass

    return ChatResponse(reply=result["reply"], sources=result["sources"])

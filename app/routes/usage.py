from fastapi import APIRouter, Depends
from app.core.auth import verify_token
from app.core import usage_service, firestore_service

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("")
async def get_usage(user_id: str = Depends(verify_token)):
    summary = usage_service.get_summary(user_id)
    used_bytes = firestore_service.get_user_size(user_id)
    summary["documents"] = {
        "used_bytes": used_bytes,
        "limit_bytes": firestore_service.LIMIT_BYTES,
    }
    return summary

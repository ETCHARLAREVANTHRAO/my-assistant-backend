import time
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from app.core.firestore_service import get_db

DAILY_LIMIT    = 50          # messages per day
MONTHLY_LIMIT  = 100_000     # tokens per month
RATE_LIMIT     = 5           # messages per minute (in-memory)

_rate_windows: dict[str, list[float]] = {}


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def _this_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")

def _get_stats(user_id: str) -> dict:
    doc = get_db().collection("users").document(user_id).collection("stats").document("usage").get()
    return doc.to_dict() or {}

def _set_stats(user_id: str, data: dict):
    get_db().collection("users").document(user_id).collection("stats").document("usage").set(data)


def check_rate_limit(user_id: str):
    now = time.time()
    window = [t for t in _rate_windows.get(user_id, []) if now - t < 60]
    if len(window) >= RATE_LIMIT:
        wait = int(61 - (now - window[0]))
        raise HTTPException(status_code=429, detail=f"Too many messages. Try again in {wait}s.")
    window.append(now)
    _rate_windows[user_id] = window


def check_and_increment_daily(user_id: str):
    today = _today()
    stats = _get_stats(user_id)
    if stats.get("daily_date") != today:
        stats["daily_date"] = today
        stats["daily_messages"] = 0
    count = stats.get("daily_messages", 0)
    if count >= DAILY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Daily limit reached ({DAILY_LIMIT} messages/day). Resets at midnight UTC.",
        )
    stats["daily_messages"] = count + 1
    _set_stats(user_id, stats)


def check_monthly_limit(user_id: str):
    month = _this_month()
    stats = _get_stats(user_id)
    if stats.get("monthly_month") != month:
        return  # new month — no usage yet
    if stats.get("monthly_tokens", 0) >= MONTHLY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Monthly token limit reached ({MONTHLY_LIMIT:,} tokens). Resets on the 1st.",
        )


def add_tokens(user_id: str, tokens: int):
    if tokens <= 0:
        return
    month = _this_month()
    stats = _get_stats(user_id)
    if stats.get("monthly_month") != month:
        stats["monthly_month"] = month
        stats["monthly_tokens"] = 0
    stats["monthly_tokens"] = stats.get("monthly_tokens", 0) + tokens
    _set_stats(user_id, stats)


def get_summary(user_id: str) -> dict:
    today = _today()
    month = _this_month()
    stats = _get_stats(user_id)

    daily_used = stats.get("daily_messages", 0) if stats.get("daily_date") == today else 0
    monthly_used = stats.get("monthly_tokens", 0) if stats.get("monthly_month") == month else 0

    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    y, m = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
    next_month = now.replace(year=y, month=m, day=1, hour=0, minute=0, second=0, microsecond=0)

    return {
        "daily": {
            "used": daily_used,
            "limit": DAILY_LIMIT,
            "resets_at": tomorrow.isoformat(),
        },
        "monthly": {
            "used": monthly_used,
            "limit": MONTHLY_LIMIT,
            "resets_at": next_month.isoformat(),
        },
    }

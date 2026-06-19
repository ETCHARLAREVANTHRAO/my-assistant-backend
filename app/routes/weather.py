from fastapi import APIRouter, HTTPException, Query
from app.models import WeatherResponse
from app.core.weather_service import get_weather

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("", response_model=WeatherResponse)
async def weather(city: str = Query(..., description="City name, e.g. 'London' or 'Hyderabad'")):
    try:
        data = await get_weather(city)
        return WeatherResponse(**data)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Weather service error: {e}")

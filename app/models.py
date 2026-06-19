from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    reply: str
    sources: list[str] = []


class DocumentUploadResponse(BaseModel):
    filename: str
    chunks_stored: int
    message: str


class DocumentListResponse(BaseModel):
    documents: list[str]


class WeatherResponse(BaseModel):
    city: str
    temperature_c: float
    feels_like_c: float
    description: str
    humidity: int
    wind_speed_ms: float
    icon: str

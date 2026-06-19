import os
import httpx

OPENWEATHER_API_KEY = os.getenv("weather")
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"


async def get_weather(city: str) -> dict:
    """Fetch current weather for a city from OpenWeatherMap."""
    if not OPENWEATHER_API_KEY:
        raise ValueError("'weather' API key is not set in .env")

    params = {
        "q": city,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
    }

    async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
        response = await client.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

    return {
        "city": data["name"],
        "temperature_c": data["main"]["temp"],
        "feels_like_c": data["main"]["feels_like"],
        "description": data["weather"][0]["description"].capitalize(),
        "humidity": data["main"]["humidity"],
        "wind_speed_ms": data["wind"]["speed"],
        "icon": data["weather"][0]["icon"],
    }

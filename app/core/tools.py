import json
import os
import httpx
from datetime import datetime
from pathlib import Path
from langchain_core.tools import tool

from .vectorstore import get_vectorstore

CALENDAR_FILE = Path("./calendar.json")
OPENWEATHER_API_KEY = os.getenv("weather")


@tool
def search_documents(query: str) -> str:
    """Search the user's uploaded documents for relevant information."""
    vs = get_vectorstore()
    docs = vs.as_retriever(search_kwargs={"k": 4}).invoke(query)
    docs = [d for d in docs if d.metadata.get("source") != "__init__"]
    if not docs:
        return "No relevant content found in uploaded documents."
    return "\n\n---\n\n".join(
        f"[{d.metadata.get('source', 'unknown')}]\n{d.page_content}" for d in docs
    )


@tool
def internet_search(query: str) -> str:
    """Search the internet for current news, sports scores, facts, or anything not in the user's documents."""
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        return DuckDuckGoSearchRun().run(query)
    except Exception as e:
        return f"Web search failed: {e}"


@tool
def get_weather(city: str) -> str:
    """Get the current weather for any city."""
    if not OPENWEATHER_API_KEY:
        return "Weather API key not configured."
    try:
        with httpx.Client(timeout=10.0, verify=False) as client:
            resp = client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric"},
            )
            resp.raise_for_status()
            d = resp.json()
        return (
            f"Weather in {d['name']}: {d['weather'][0]['description'].capitalize()}, "
            f"{d['main']['temp']}°C (feels like {d['main']['feels_like']}°C), "
            f"Humidity: {d['main']['humidity']}%, Wind: {d['wind']['speed']} m/s"
        )
    except Exception as e:
        return f"Could not fetch weather for '{city}': {e}"


@tool
def get_datetime(timezone: str = "") -> str:
    """Get the current date and time. The timezone parameter is optional and ignored."""
    now = datetime.now()
    return now.strftime("Today is %A, %B %d, %Y. The time is %I:%M %p.")


@tool
def add_calendar_event(title: str, date: str, time: str = "", notes: str = "") -> str:
    """Add an event to the calendar. Date must be in YYYY-MM-DD format. Time is optional (HH:MM)."""
    events = json.loads(CALENDAR_FILE.read_text()) if CALENDAR_FILE.exists() else []
    events.append({"title": title, "date": date, "time": time, "notes": notes})
    events.sort(key=lambda e: (e["date"], e.get("time", "")))
    CALENDAR_FILE.write_text(json.dumps(events, indent=2))
    time_str = f" at {time}" if time else ""
    return f"Event '{title}' added for {date}{time_str}."


@tool
def get_calendar_events(date_filter: str = "all") -> str:
    """Get upcoming calendar events. Pass a date in YYYY-MM-DD format to filter, or 'all' for all upcoming events."""
    if not CALENDAR_FILE.exists():
        return "No calendar events found."
    events = json.loads(CALENDAR_FILE.read_text())
    today = datetime.now().strftime("%Y-%m-%d")
    upcoming = [e for e in events if e["date"] >= today]
    if date_filter and date_filter != "all":
        upcoming = [e for e in upcoming if e["date"] == date_filter]
    if not upcoming:
        return "No upcoming events."
    lines = []
    for e in upcoming[:10]:
        line = f"• {e['date']}"
        if e.get("time"):
            line += f" at {e['time']}"
        line += f": {e['title']}"
        if e.get("notes"):
            line += f" — {e['notes']}"
        lines.append(line)
    return "\n".join(lines)


def get_all_tools():
    return [
        internet_search,
        get_weather,
        get_datetime,
        add_calendar_event,
        get_calendar_events,
    ]

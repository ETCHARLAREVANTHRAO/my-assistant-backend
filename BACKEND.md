# backend/

Python FastAPI server — handles all AI, RAG, tool calling, and weather logic.

## Folder Structure

```
backend/
├── app/
│   ├── main.py              ← FastAPI app, CORS middleware, route registration
│   ├── models.py            ← Pydantic request/response schemas
│   ├── routes/
│   │   ├── chat.py          ← POST /chat
│   │   ├── documents.py     ← GET/POST/DELETE /documents
│   │   └── weather.py       ← GET /weather?city=...
│   └── core/
│       ├── rag.py           ← Chat loop: RAG + tool calling + conversation history
│       ├── tools.py         ← LangChain @tool definitions
│       ├── vectorstore.py   ← FAISS + HuggingFace embeddings (dual: local / Inference API)
│       └── weather_service.py ← OpenWeatherMap HTTP client
├── faiss_index/             ← Created at runtime; stores vector embeddings
├── logs.txt                 ← Debug log appended on every chat turn
├── calendar.json            ← Calendar events (created at runtime)
├── requirements.txt
├── Dockerfile
├── render.yaml              ← Render deployment config
└── .env.example
```

## Key Design Decisions

- **LLM**: Groq `qwen/qwen3-32b` — fast inference, free tier available.
- **Vector store**: FAISS (not ChromaDB) — no native dependencies, works on Render free tier.
- **Embeddings**: Dual mode:
  - Local dev (no `HF_API_TOKEN`): `sentence-transformers/all-MiniLM-L6-v2` downloaded locally (~90 MB).
  - Render (with `HF_API_TOKEN`): HuggingFace Inference API — no local model, avoids OOM on 512 MB RAM.
- **Tool calling**: Manual `bind_tools()` loop (up to 5 iterations) — avoids `AgentExecutor` compatibility issues with Groq.
- **Document search**: FAISS queried directly before the LLM call; not exposed as a tool (prevents Groq hallucinating tool calls for it).
- **SSL**: All outbound HTTP clients use `verify=False` for corporate network compatibility.
- **Chunking**: Files split by character size (800 chars, 100 overlap). Markdown also split by headers first.

## Supported Document Types

| Extension | Parser |
|---|---|
| `.pdf` | `pypdf` |
| `.docx` | `python-docx` |
| `.md`, `.txt` | plain text decode |
| `.jpg`, `.png`, `.bmp`, `.tiff`, `.webp` | `pytesseract` OCR |

## Available Tools

| Tool | Description |
|---|---|
| `internet_search` | DuckDuckGo web search (`DDGS(verify=False)`) |
| `get_weather` | Current weather via OpenWeatherMap |
| `get_datetime` | Current date and time |
| `add_calendar_event` | Save an event to `calendar.json` |
| `get_calendar_events` | List upcoming calendar events |

## Setup (local dev)

```bash
cd backend

# Activate venv
..\my_assistant\Scripts\activate    # Windows

# Install deps
pip install -r requirements.txt

# Create your .env
copy .env.example .env
# Fill in GROQ_API_KEY and weather (OpenWeatherMap key)
# Leave HF_API_TOKEN blank for local dev (uses local model)

# Run
uvicorn app.main:app --reload --port 8000
```

API docs: `http://localhost:8000/docs`

Debug logs: `backend/logs.txt` (appended live, view with any text editor)

## Deploy to Render

1. Push repo to GitHub
2. Create a new Render Web Service → connect GitHub repo → set root to `backend/`
3. Set environment variables:
   - `GROQ_API_KEY`
   - `weather` (OpenWeatherMap key)
   - `HF_API_TOKEN` (HuggingFace token — required on Render)
   - `CHROMA_PERSIST_DIR=/app/faiss_index`
4. Render auto-detects `Dockerfile` and builds

Live backend: `https://my-assistant-backend-nxwg.onrender.com`

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/chat` | `{ message }` → `{ reply, sources }` |
| `GET` | `/documents` | List ingested documents |
| `POST` | `/documents/upload` | Upload any supported file (multipart) |
| `DELETE` | `/documents/{filename}` | Remove a document |
| `GET` | `/weather?city=...` | Current weather for a city |
| `GET` | `/health` | Health check |

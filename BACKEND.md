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
│       ├── vectorstore.py   ← Supabase/pgvector store + fastembed embeddings
│       ├── drive_sync.py    ← Google Drive → RAG document auto-import
│       ├── auth.py          ← Firebase ID token verification
│       ├── firestore_service.py ← Per-user document metadata + Drive sync state
│       └── weather_service.py ← OpenWeatherMap HTTP client
├── supabase_setup.sql       ← One-time SQL: pgvector table + similarity-search RPC
├── logs.txt                 ← Debug log appended on every chat turn
├── calendar.json            ← Calendar events (created at runtime)
├── requirements.txt
├── Dockerfile
├── render.yaml              ← Render deployment config
└── .env.example
```

## Key Design Decisions

- **LLM**: Groq `llama-3.3-70b-versatile` — fast inference, free tier available.
- **Vector store**: Supabase (Postgres + `pgvector`) — persists natively across restarts, similarity search via a `match_document_chunks` RPC (pgvector's `<=>` operator isn't reachable through normal PostgREST table filters).
- **Embeddings**: `fastembed` (`BAAI/bge-small-en-v1.5`, 384-dim, ONNX) — no PyTorch, runs locally on both dev and Render.
- **Tool calling**: Manual `bind_tools()` loop (up to 5 iterations) — avoids `AgentExecutor` compatibility issues with Groq.
- **Document search**: Supabase queried directly before the LLM call; not exposed as a tool (prevents Groq hallucinating tool calls for it).
- **Drive sync**: `POST /documents/drive-sync` lists files in a shared Drive folder (service account, read-only) and ingests any new/changed ones into the calling user's document store — same pipeline as manual upload.
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
# Fill in GROQ_API_KEY, weather (OpenWeatherMap key), SUPABASE_URL, SUPABASE_SERVICE_KEY
# Run backend/supabase_setup.sql once in the Supabase SQL Editor before first use

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
   - `FIREBASE_SERVICE_ACCOUNT_JSON` (full service account JSON, one line)
   - `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
   - `GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON`, `GOOGLE_DRIVE_FOLDER_ID` (optional — only if Drive sync is used)
4. Render auto-detects `Dockerfile` and builds

Live backend: `https://my-assistant-backend-nxwg.onrender.com`

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/chat` | `{ message }` → `{ reply, sources }` |
| `GET` | `/documents` | List ingested documents |
| `POST` | `/documents/upload` | Upload any supported file (multipart) |
| `DELETE` | `/documents/{filename}` | Remove a document |
| `POST` | `/documents/drive-sync` | Sync new/changed files from the configured Drive folder |
| `GET` | `/weather?city=...` | Current weather for a city |
| `GET` | `/health` | Health check |

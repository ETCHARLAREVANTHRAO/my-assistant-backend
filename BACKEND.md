# backend/

Python FastAPI server — handles all AI, RAG, and weather logic.

## Folder Structure

```
backend/
├── app/
│   ├── main.py          ← FastAPI app, CORS middleware, route registration
│   ├── models.py        ← Pydantic request/response schemas
│   ├── routes/
│   │   ├── chat.py      ← POST /chat — sends message through RAG pipeline
│   │   ├── documents.py ← GET/POST/DELETE /documents — manage Markdown files
│   │   └── weather.py   ← GET /weather?city=... — current weather
│   └── core/
│       ├── rag.py           ← LangChain RAG: ingest, retrieve, chat with Groq (Llama 3.3 70B)
│       ├── vectorstore.py   ← ChromaDB setup + HuggingFace embeddings
│       └── weather_service.py ← OpenWeatherMap HTTP client
├── chroma_db/           ← Created at runtime; stores vector embeddings
├── requirements.txt
├── Dockerfile
├── railway.json         ← Railway deployment config
└── .env.example
```

## Key Design Decisions

- **Embeddings**: Uses `all-MiniLM-L6-v2` (free, runs locally) instead of a paid embedding API. Downloads ~90 MB on first run.
- **LLM**: Groq `llama-3.3-70b-versatile` — very fast inference via Groq's hardware, free tier available.
- **Chunking**: Markdown is first split by headers (h1/h2/h3), then by character size (800 chars, 100 overlap) to preserve document structure.
- **ChromaDB**: Persists to disk (`./chroma_db`) so documents survive restarts. On Railway, add a volume mount at `/app/chroma_db` to make it truly persistent.

## Setup (local dev)

```bash
# From the my_assistant root
cd backend

# Activate the existing venv
..\my_assistant\Scripts\activate    # Windows

# Install deps
pip install -r requirements.txt

# Create your .env
copy .env.example .env
# Fill in ANTHROPIC_API_KEY and OPENWEATHER_API_KEY

# Run
uvicorn app.main:app --reload --port 8000
```

API docs available at `http://localhost:8000/docs`

## Deploy to Railway

1. Push this repo to GitHub
2. Create a new Railway project → "Deploy from GitHub repo"
3. Set environment variables: `GROQ_API_KEY`, `weather` (OpenWeatherMap key), `CHROMA_PERSIST_DIR=/app/chroma_db`
4. Add a volume mount at `/app/chroma_db` for persistence
5. Railway auto-detects the `Dockerfile` and builds

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/chat` | `{ message }` → `{ reply, sources }` |
| `GET` | `/documents` | List ingested documents |
| `POST` | `/documents/upload` | Upload a `.md` file (multipart) |
| `DELETE` | `/documents/{filename}` | Remove a document |
| `GET` | `/weather?city=...` | Current weather for a city |
| `GET` | `/health` | Health check |

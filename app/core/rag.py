import io
import os
import httpx
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from .vectorstore import add_documents, delete_by_source, list_sources
from .tools import get_all_tools

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
_http_client = httpx.Client(verify=False)
_async_http_client = httpx.AsyncClient(verify=False)

SYSTEM_PROMPT = """You are a helpful personal AI assistant.

Document context from the user's uploaded files may be provided below. Follow these rules:
1. If the question is about the user's documents, resume, notes, or files — answer using the document context provided.
2. If the question is about the current date or time — call get_datetime.
3. If the question is about weather — call get_weather.
4. If the question is about news, sports, or facts not in the documents — call internet_search.
5. If the question is about calendar events — call add_calendar_event or get_calendar_events.
6. Only call one tool at a time. Never call a tool if the document context already answers the question.

Be concise, accurate, and friendly."""


_conversation_history: list = []
MAX_HISTORY_TURNS = 10  # keep last 10 messages (5 user + 5 assistant)


def _get_llm() -> ChatGroq:
    return ChatGroq(
        model="qwen/qwen3-32b",
        api_key=GROQ_API_KEY,
        max_tokens=1024,
        http_client=_http_client,
        http_async_client=_async_http_client,
    )




def _extract_text(content_bytes: bytes, filename: str) -> str:
    """Extract plain text from PDF, DOCX, image, or text file."""
    ext = filename.rsplit(".", 1)[-1].lower()

    if ext == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content_bytes))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)

    if ext == "docx":
        from docx import Document as DocxDocument
        doc = DocxDocument(io.BytesIO(content_bytes))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())

    if ext in ("jpg", "jpeg", "png", "bmp", "tiff", "webp"):
        try:
            import pytesseract
            from PIL import Image
            image = Image.open(io.BytesIO(content_bytes))
            return pytesseract.image_to_string(image)
        except Exception as e:
            return f"[Image OCR failed: {e}]"

    # Default: plain text / markdown
    return content_bytes.decode("utf-8", errors="ignore")


def ingest_document(content_bytes: bytes, filename: str) -> int:
    """Parse any supported file type, chunk it, and store in FAISS. Returns chunk count."""
    text = _extract_text(content_bytes, filename)
    if not text.strip():
        raise ValueError("No text could be extracted from the file.")

    ext = filename.rsplit(".", 1)[-1].lower()
    char_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)

    if ext == "md":
        header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
            strip_headers=False,
        )
        docs = char_splitter.split_documents(header_splitter.split_text(text))
    else:
        docs = char_splitter.create_documents([text])

    for doc in docs:
        doc.metadata["source"] = filename
    add_documents(docs)
    return len(docs)


def ingest_markdown(content: str, filename: str) -> int:
    """Legacy wrapper kept for compatibility."""
    return ingest_document(content.encode(), filename)


def delete_document(filename: str):
    delete_by_source(filename)


def list_documents() -> list[str]:
    return list_sources()


def _search_docs_sync(query: str) -> str:
    """Search vectorstore and return top chunks (excluding the bootstrap placeholder)."""
    from .vectorstore import get_vectorstore
    try:
        vs = get_vectorstore()
        docs = vs.similarity_search(query, k=4)
        docs = [d for d in docs if d.metadata.get("source") != "__init__"]
        if not docs:
            return ""
        return "\n\n---\n\n".join(
            f"[{d.metadata.get('source', 'unknown')}]\n{d.page_content}" for d in docs
        )
    except Exception:
        return ""


async def chat(message: str) -> dict:
    """RAG + tool-calling chat with conversation history."""
    global _conversation_history

    doc_context = _search_docs_sync(message)

    from .tools import get_weather, get_datetime, add_calendar_event, get_calendar_events, internet_search
    action_tools = [get_weather, get_datetime, add_calendar_event, get_calendar_events, internet_search]
    tools_by_name = {t.name: t for t in action_tools}
    llm_with_tools = _get_llm().bind_tools(action_tools)
    llm_plain = _get_llm()

    system_with_context = SYSTEM_PROMPT
    if doc_context:
        system_with_context += f"\n\n--- Relevant content from user's documents ---\n{doc_context}\n---"

    # Build messages: system + recent history + current message
    messages = (
        [SystemMessage(content=system_with_context)]
        + _conversation_history[-MAX_HISTORY_TURNS:]
        + [HumanMessage(content=message)]
    )

    reply = None
    try:
        for _ in range(5):
            response = await llm_with_tools.ainvoke(messages)
            messages.append(response)

            if not response.tool_calls:
                reply = response.content or "Sorry, I could not generate a response."
                break

            for tc in response.tool_calls:
                tool = tools_by_name.get(tc["name"])
                if tool:
                    try:
                        result = await tool.ainvoke(tc["args"])
                    except Exception as e:
                        result = f"Tool error: {e}"
                else:
                    result = f"Unknown tool: {tc['name']}"
                messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

    except Exception:
        fallback = await llm_plain.ainvoke([
            SystemMessage(content="You are a helpful assistant. Answer directly and concisely. Do not call any tools."),
            HumanMessage(content=f"{system_with_context}\n\nUser question: {message}")
        ])
        reply = fallback.content or "Sorry, I could not generate a response."

    if not reply:
        reply = "Sorry, I could not complete the request."

    # Save this turn to history
    _conversation_history.append(HumanMessage(content=message))
    _conversation_history.append(AIMessage(content=reply))
    # Trim to max turns
    if len(_conversation_history) > MAX_HISTORY_TURNS:
        _conversation_history = _conversation_history[-MAX_HISTORY_TURNS:]

    return {"reply": reply, "sources": []}


def clear_history():
    global _conversation_history
    _conversation_history = []

import os
import httpx
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from .vectorstore import get_vectorstore, add_documents, delete_by_source, list_sources

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Corporate networks inject self-signed SSL certs; bypass verification for Groq calls
_http_client = httpx.Client(verify=False)

SYSTEM_PROMPT = """You are a helpful personal assistant. Use the provided document context to answer the user's question accurately.
If the context doesn't contain relevant information, answer from your general knowledge and say so.
Keep answers concise and friendly.

Context from documents:
{context}
"""


def _get_llm():
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=GROQ_API_KEY,
        max_tokens=1024,
        http_client=_http_client,
    )


def ingest_markdown(content: str, filename: str) -> int:
    """Split a markdown document and store chunks in FAISS. Returns chunk count."""
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
        strip_headers=False,
    )
    header_chunks = header_splitter.split_text(content)

    char_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    docs = char_splitter.split_documents(header_chunks)

    for doc in docs:
        doc.metadata["source"] = filename

    add_documents(docs)
    return len(docs)


def delete_document(filename: str):
    delete_by_source(filename)


def list_documents() -> list[str]:
    return list_sources()


def chat(message: str) -> dict:
    """Retrieve relevant chunks then generate a reply with Groq."""
    vs = get_vectorstore()
    retriever = vs.as_retriever(search_kwargs={"k": 5})
    relevant_docs: list[Document] = retriever.invoke(message)

    # Filter out the bootstrap placeholder
    relevant_docs = [d for d in relevant_docs if d.metadata.get("source") != "__init__"]

    context = "\n\n---\n\n".join(d.page_content for d in relevant_docs) if relevant_docs else "No documents uploaded yet."
    sources = list({d.metadata.get("source", "") for d in relevant_docs if d.metadata.get("source")})

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{question}"),
    ])

    chain = (
        {"context": lambda _: context, "question": RunnablePassthrough()}
        | prompt
        | _get_llm()
        | StrOutputParser()
    )

    reply = chain.invoke(message)
    return {"reply": reply, "sources": sources}

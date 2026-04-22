import json
import re
import logging
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models import DocumentChunk, AgentDocument

logger = logging.getLogger(__name__)

_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
_embedding_model = None
_MIN_CHUNK_WORDS = 8
_MIN_SIMILARITY = 0.10


def _get_model():
    global _embedding_model
    if _embedding_model is None:
        from fastembed import TextEmbedding
        _embedding_model = TextEmbedding(model_name=_MODEL_NAME)
    return _embedding_model


def _embed_sync(text: str) -> list[float]:
    return next(_get_model().embed([text])).tolist()


async def embed_text(text: str) -> list[float]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _embed_sync, text)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    import numpy as np
    av, bv = np.array(a, dtype=np.float32), np.array(b, dtype=np.float32)
    denom = np.linalg.norm(av) * np.linalg.norm(bv)
    return float(np.dot(av, bv) / denom) if denom > 0 else 0.0


def extract_chunks_from_pdf(file_path: str) -> list[tuple[int, str]]:
    from pypdf import PdfReader
    reader = PdfReader(file_path)
    chunks = []
    for i, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").strip()
        if text and len(text.split()) >= _MIN_CHUNK_WORDS:
            chunks.append((i, text))
    return chunks


async def get_active_document(db: AsyncSession) -> AgentDocument | None:
    return (await db.execute(
        select(AgentDocument).where(AgentDocument.is_active == True)
    )).scalar_one_or_none()


async def search_relevant_chunks(query: str, db: AsyncSession, top_k: int = 3) -> list[str]:
    doc = await get_active_document(db)
    if not doc:
        return []

    chunks = (await db.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
    )).scalars().all()
    if not chunks:
        return []

    # Semantic search when embeddings are available
    if chunks[0].embedding:
        query_vec = await embed_text(query)
        scored = [
            (_cosine_similarity(query_vec, json.loads(c.embedding)), c.chunk_text)
            for c in chunks
        ]
        scored.sort(key=lambda x: -x[0])
        return [text for score, text in scored[:top_k] if score >= _MIN_SIMILARITY]

    # Fallback: keyword search for chunks without embeddings
    words = {w.lower() for w in re.findall(r'\w+', query) if len(w) > 3}
    if not words:
        return [c.chunk_text for c in chunks[:top_k]]

    scored = []
    for chunk in chunks:
        chunk_words = set(re.findall(r'\w+', chunk.chunk_text.lower()))
        score = sum(1 for w in words if w in chunk_words)
        if score > 0:
            scored.append((score, chunk.chunk_text))

    scored.sort(key=lambda x: -x[0])
    return [text for _, text in scored[:top_k]]

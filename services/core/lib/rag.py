"""RAG service using pgvector (PostgreSQL) + Ollama embeddings."""
import json
import logging
import asyncpg
import httpx
from typing import Any
from lib.config import settings

logger = logging.getLogger(__name__)


async def _get_embedding(text: str) -> list[float]:
    """Generate embedding for text using Ollama."""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.ollama_api_url}/api/embeddings",
                json={"model": settings.ollama_model, "prompt": text},
            )
            if resp.status_code == 200:
                data = resp.json()
                vec = data.get("embedding") or []
                if isinstance(vec, list) and vec:
                    return vec
    except Exception as exc:
        logger.warning("Embedding generation failed: %s", exc)
    return []


async def search(query: str, limit: int = 3) -> list[dict]:
    """Search RAG documents by semantic similarity."""
    embedding = await _get_embedding(query)
    if not embedding:
        logger.warning("Empty embedding for query, skipping RAG search")
        return []

    dsn = (
        f"postgresql://{settings.db_rag_user}:{settings.db_rag_password}"
        f"@{settings.db_rag_host}:{settings.db_rag_port}/{settings.db_rag_name}"
    )
    conn = await asyncpg.connect(dsn, timeout=15)
    try:
        rows = await conn.fetch(
            "SELECT content, metadata, 1 - (embedding <=> $1::vector) AS score "
            "FROM documents ORDER BY embedding <=> $1::vector LIMIT $2",
            str(embedding),
            limit,
        )
        results = []
        for r in rows:
            results.append({
                "content": r["content"],
                "metadata": r["metadata"],
                "score": float(r["score"]),
            })
        return results
    except Exception as exc:
        logger.error("RAG search failed: %s", exc)
        return []
    finally:
        await conn.close()
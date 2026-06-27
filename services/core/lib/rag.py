"""RAG service: unified interface delegating to configured backend (pgvector or turbovec)."""
import logging
from lib.rag_factory import get_backend

logger = logging.getLogger(__name__)


async def search(query: str, limit: int = 3) -> list[dict]:
    """Search RAG documents by semantic similarity using configured backend."""
    backend = get_backend()
    try:
        return await backend.search(query, limit=limit)
    except Exception as exc:
        logger.error("RAG search failed: %s", exc)
        return []

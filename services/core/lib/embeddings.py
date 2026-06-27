"""Shared embedding utilities for RAG backends."""
import httpx
import logging
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

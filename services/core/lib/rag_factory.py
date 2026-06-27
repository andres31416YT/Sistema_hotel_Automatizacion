"""RAG factory: selects backend based on RAG_PROVIDER setting."""
from lib.config import settings
from lib.rag_interface import RAGBackend
from lib.rag_pgvector import PgVectorBackend
from lib.rag_turbovec import TurboVecBackend

_backend: RAGBackend | None = None


def get_backend() -> RAGBackend:
    global _backend
    if _backend is None:
        provider = getattr(settings, "rag_provider", "pgvector") or "pgvector"
        if provider == "turbovec":
            _backend = TurboVecBackend()
        else:
            _backend = PgVectorBackend()
    return _backend

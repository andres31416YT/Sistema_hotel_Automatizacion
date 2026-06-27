"""Abstract interface for RAG backends."""
from abc import ABC, abstractmethod
from typing import Any


class RAGBackend(ABC):
    @abstractmethod
    async def ingest_document(self, text: str, metadata: dict[str, Any] | None = None) -> int:
        """Index a document and return its assigned document id."""
        ...

    @abstractmethod
    async def search(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        """Return list of dicts with keys: content, metadata, score."""
        ...

    @abstractmethod
    async def delete_document(self, doc_id: int) -> None:
        """Remove a document from the index by its id."""
        ...

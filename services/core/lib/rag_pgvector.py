"""RAG backend using pgvector in PostgreSQL."""
import asyncpg
import json
import logging
from typing import Any
from lib.rag_interface import RAGBackend
from lib.config import settings

logger = logging.getLogger(__name__)


class PgVectorBackend(RAGBackend):
    def __init__(self):
        self.dsn = (
            f"postgresql://{settings.db_rag_user}:{settings.db_rag_password}"
            f"@{settings.db_rag_host}:{settings.db_rag_port}/{settings.db_rag_name}"
        )

    async def _get_conn(self):
        return await asyncpg.connect(self.dsn, timeout=15)

    async def ingest_document(self, text: str, metadata: dict[str, Any] | None = None) -> int:
        from lib.rag import _get_embedding
        embedding = await _get_embedding(text)
        if not embedding:
            raise RuntimeError("Failed to generate embedding for document")

        conn = await self._get_conn()
        try:
            row = await conn.fetchrow(
                "INSERT INTO documents (content, embedding, metadata) VALUES ($1, $2::vector, $3) RETURNING id",
                text,
                str(embedding),
                json.dumps(metadata or {}),
            )
            doc_id = int(row["id"])
            logger.info("PgVector ingested document id=%s", doc_id)
            return doc_id
        finally:
            await conn.close()

    async def search(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        from lib.rag import _get_embedding
        embedding = await _get_embedding(query)
        if not embedding:
            logger.warning("Empty embedding for query in PgVector")
            return []

        conn = await self._get_conn()
        try:
            rows = await conn.fetch(
                "SELECT id, content, metadata, 1 - (embedding <=> $1::vector) AS score "
                "FROM documents ORDER BY embedding <=> $1::vector LIMIT $2",
                str(embedding),
                limit,
            )
            results = []
            for r in rows:
                results.append({
                    "id": int(r["id"]),
                    "content": r["content"],
                    "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                    "score": float(r["score"]),
                })
            return results
        finally:
            await conn.close()

    async def delete_document(self, doc_id: int) -> None:
        conn = await self._get_conn()
        try:
            await conn.execute("DELETE FROM documents WHERE id = $1", doc_id)
            logger.info("PgVector deleted document id=%s", doc_id)
        finally:
            await conn.close()

"""RAG backend using turbovec (TurboQuant) for ultra-compressed vector search."""
import json
import logging
import os
from typing import Any
from lib.rag_interface import RAGBackend
from lib.config import settings

logger = logging.getLogger(__name__)


class TurboVecBackend(RAGBackend):
    def __init__(self):
        self.index_path = settings.rag_turbovec_path
        self.bit_width = settings.rag_turbovec_bit_width
        self._index = None
        self._ensure_index_loaded()

    def _ensure_index_loaded(self):
        try:
            from turbovec import IdMapIndex, TurboQuantIndex
        except ImportError:
            raise RuntimeError(
                "turbovec package is not installed. "
                "Install it with: pip install turbovec[langchain]"
            )

        os.makedirs(os.path.dirname(self.index_path) or ".", exist_ok=True)

        if os.path.exists(self.index_path):
            try:
                self._index = IdMapIndex(TurboQuantIndex(bit_width=self.bit_width))
                self._index.load(self.index_path)
                logger.info(
                    "TurboVec index loaded from %s (bit_width=%s)",
                    self.index_path,
                    self.bit_width,
                )
            except Exception as exc:
                logger.warning("Failed to load turbovec index, creating new one: %s", exc)
                self._index = IdMapIndex(TurboQuantIndex(bit_width=self.bit_width))
        else:
            self._index = IdMapIndex(TurboQuantIndex(bit_width=self.bit_width))
            logger.info(
                "TurboVec new index initialized (bit_width=%s, path=%s)",
                self.bit_width,
                self.index_path,
            )

    def _persist(self):
        if self._index is not None:
            self._index.write(self.index_path)

    async def _get_conn(self):
        import asyncpg
        dsn = (
            f"postgresql://{settings.db_rag_user}:{settings.db_rag_password}"
            f"@{settings.db_rag_host}:{settings.db_rag_port}/{settings.db_rag_name}"
        )
        return await asyncpg.connect(dsn, timeout=15)

    async def ingest_document(self, text: str, metadata: dict[str, Any] | None = None) -> int:
        from lib.rag import _get_embedding

        embedding = await _get_embedding(text)
        if not embedding:
            raise RuntimeError("Failed to generate embedding for document")

        conn = await self._get_conn()
        try:
            row = await conn.fetchrow(
                "INSERT INTO documents (content, metadata) VALUES ($1, $2) RETURNING id",
                text,
                json.dumps(metadata or {}),
            )
            doc_id = int(row["id"])
        finally:
            await conn.close()

        self._index.add(doc_id, embedding)
        self._persist()
        logger.info("TurboVec ingested document id=%s", doc_id)
        return doc_id

    async def search(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        from lib.rag import _get_embedding

        embedding = await _get_embedding(query)
        if not embedding:
            logger.warning("Empty embedding for query in TurboVec")
            return []

        try:
            raw_results = self._index.search(embedding, k=limit)
        except Exception as exc:
            logger.error("TurboVec search failed: %s", exc)
            return []

        if not raw_results:
            return []

        doc_ids = []
        for item in raw_results:
            if hasattr(item, "id"):
                doc_ids.append(int(item.id))
            elif isinstance(item, (tuple, list)) and len(item) >= 1:
                doc_ids.append(int(item[0]))
            elif isinstance(item, dict):
                doc_ids.append(int(item.get("id", 0)))
            else:
                doc_ids.append(int(item))

        doc_ids = [d for d in doc_ids if d > 0]
        if not doc_ids:
            return []

        conn = await self._get_conn()
        try:
            rows = await conn.fetch(
                "SELECT id, content, metadata FROM documents WHERE id = ANY($1::int[])",
                doc_ids,
            )
            by_id = {int(r["id"]): r for r in rows}
        finally:
            await conn.close()

        results = []
        for idx, doc_id in enumerate(doc_ids):
            row = by_id.get(doc_id)
            if row is None:
                continue
            score = 1.0 - (idx * 0.05)
            results.append({
                "id": doc_id,
                "content": row["content"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                "score": float(score),
            })
        return results

    async def delete_document(self, doc_id: int) -> None:
        conn = await self._get_conn()
        try:
            await conn.execute("DELETE FROM documents WHERE id = $1", doc_id)
        finally:
            await conn.close()

        self._index.remove(doc_id)
        self._persist()
        logger.info("TurboVec deleted document id=%s", doc_id)

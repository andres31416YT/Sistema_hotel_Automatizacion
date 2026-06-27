"""RAG backend using turbovec (TurboQuant) for ultra-compressed vector search."""
import json
import logging
import os
from typing import Any
from lib.rag_interface import RAGBackend
from lib.config import settings
from lib.embeddings import _get_embedding
from turbovec import TurboQuantIndex
import numpy as np

logger = logging.getLogger(__name__)


class TurboVecBackend(RAGBackend):
    def __init__(self):
        self.index_path = settings.rag_turbovec_path
        self.mapping_path = self.index_path + ".json"
        self.bit_width = settings.rag_turbovec_bit_width
        self.dimension = None
        self._index = None
        self._id_to_pos: dict[int, int] = {}
        self._pos_to_id: list[int] = []
        self._ensure_index_loaded()

    def _ensure_index_loaded(self):
        os.makedirs(os.path.dirname(self.index_path) or ".", exist_ok=True)

        if os.path.exists(self.index_path):
            try:
                self._index = TurboQuantIndex.load(self.index_path)
                self.dimension = getattr(self._index, "dim", None)
                logger.info(
                    "TurboVec index loaded from %s (bit_width=%s, dim=%s)",
                    self.index_path,
                    self.bit_width,
                    self.dimension,
                )
            except Exception as exc:
                logger.warning("Failed to load turbovec index, creating new one: %s", exc)
                self._index = None
                self.dimension = None
        else:
            self._index = None
            self.dimension = None
            logger.info(
                "TurboVec new index placeholder initialized (bit_width=%s, path=%s)",
                self.bit_width,
                self.index_path,
            )

        if os.path.exists(self.mapping_path):
            try:
                with open(self.mapping_path, "r") as f:
                    data = json.load(f)
                self._id_to_pos = {int(k): int(v) for k, v in data.get("id_to_pos", {}).items()}
                self._pos_to_id = [int(x) for x in data.get("pos_to_id", [])]
            except Exception as exc:
                logger.warning("Failed to load turbovec mapping, starting fresh: %s", exc)
                self._id_to_pos = {}
                self._pos_to_id = []
        else:
            self._id_to_pos = {}
            self._pos_to_id = []

        if self._index is None:
            dim = self.dimension or 2048
            self._index = TurboQuantIndex(dim=dim, bit_width=self.bit_width)
            if self.dimension is None:
                self.dimension = dim

    def _persist(self):
        if self._index is not None:
            self._index.write(self.index_path)
        with open(self.mapping_path, "w") as f:
            json.dump({
                "id_to_pos": {str(k): v for k, v in self._id_to_pos.items()},
                "pos_to_id": self._pos_to_id,
            }, f)

    async def _get_conn(self):
        import asyncpg
        dsn = (
            f"postgresql://{settings.db_rag_user}:{settings.db_rag_password}"
            f"@{settings.db_rag_host}:{settings.db_rag_port}/{settings.db_rag_name}"
        )
        return await asyncpg.connect(dsn, timeout=15)

    async def ingest_document(self, text: str, metadata: dict[str, Any] | None = None) -> int:
        embedding = await _get_embedding(text)
        if not embedding:
            raise RuntimeError("Failed to generate embedding for document")

        vec = np.asarray(embedding, dtype=np.float32).reshape(1, -1)
        if self.dimension is None:
            self.dimension = vec.shape[1]
            self._index = TurboQuantIndex(dim=self.dimension, bit_width=self.bit_width)
        elif vec.shape[1] != self.dimension:
            raise RuntimeError(f"Embedding dimension mismatch: expected {self.dimension}, got {vec.shape[1]}")

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

        self._index.add(vec)
        pos = len(self._pos_to_id)
        self._id_to_pos[doc_id] = pos
        self._pos_to_id.append(doc_id)
        self._persist()
        logger.info("TurboVec ingested document id=%s at pos=%s", doc_id, pos)
        return doc_id

    async def search(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        embedding = await _get_embedding(query)
        if not embedding:
            logger.warning("Empty embedding for query in TurboVec")
            return []

        vec = np.asarray(embedding, dtype=np.float32).reshape(1, -1)
        if self.dimension is not None and vec.shape[1] != self.dimension:
            logger.error("Embedding dimension mismatch in TurboVec search: expected %s, got %s", self.dimension, vec.shape[1])
            return []

        if self._index is None:
            logger.warning("TurboVec index not initialized")
            return []

        try:
            scores, ids = self._index.search(vec, k=limit)
        except Exception as exc:
            logger.error("TurboVec search failed: %s", exc)
            return []

        if ids is None or ids.size == 0:
            return []

        positions = [int(i) for i in ids[0] if int(i) >= 0]
        if not positions:
            return []

        doc_ids = []
        for pos in positions:
            if 0 <= pos < len(self._pos_to_id):
                doc_id = self._pos_to_id[pos]
                if doc_id > 0:
                    doc_ids.append(doc_id)

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

        pos = self._id_to_pos.pop(doc_id, None)
        if pos is not None and 0 <= pos < len(self._pos_to_id):
            self._pos_to_id[pos] = -1
        self._persist()
        logger.info("TurboVec deleted document id=%s", doc_id)

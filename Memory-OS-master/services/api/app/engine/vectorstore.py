"""VectorStore abstraction.

MEMORY OS never generates embeddings — callers supply them. This module only
stores and searches vectors the client provided.

The default implementation targets PostgreSQL + pgvector. A pure-Python
InMemoryVectorStore is provided so the engine is testable without a database and
so local dev works with the SQLite fallback. Qdrant/Pinecone/Weaviate are
declared as extension points but intentionally left unimplemented rather than
faked.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class VectorHit:
    memory_id: str
    distance: float  # cosine distance, lower is closer


class VectorStore(ABC):
    @abstractmethod
    async def upsert(self, tenant_id: str, memory_id: str, embedding: list[float]) -> None: ...

    @abstractmethod
    async def search(
        self, tenant_id: str, embedding: list[float], *, limit: int
    ) -> list[VectorHit]: ...

    @abstractmethod
    async def delete(self, tenant_id: str, memory_id: str) -> None: ...


class InMemoryVectorStore(VectorStore):
    """Deterministic reference implementation. Tenant-isolated by construction."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, list[float]]] = {}

    async def upsert(self, tenant_id: str, memory_id: str, embedding: list[float]) -> None:
        self._data.setdefault(tenant_id, {})[memory_id] = list(embedding)

    async def search(self, tenant_id: str, embedding: list[float], *, limit: int) -> list[VectorHit]:
        bucket = self._data.get(tenant_id, {})
        hits = [
            VectorHit(memory_id=mid, distance=_cosine_distance(embedding, vec))
            for mid, vec in bucket.items()
        ]
        hits.sort(key=lambda h: (h.distance, h.memory_id))
        return hits[:limit]

    async def delete(self, tenant_id: str, memory_id: str) -> None:
        self._data.get(tenant_id, {}).pop(memory_id, None)


class PgVectorStore(VectorStore):
    """PostgreSQL + pgvector implementation.

    Uses the `memory_embeddings` table with an ivfflat/hnsw index and cosine ops.
    Tenant isolation is enforced in every WHERE clause.
    """

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def upsert(self, tenant_id: str, memory_id: str, embedding: list[float]) -> None:
        from sqlalchemy import text

        async with self._session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO memory_embeddings (memory_id, tenant_id, embedding) "
                    "VALUES (:mid, :tid, :emb) "
                    "ON CONFLICT (memory_id) DO UPDATE SET embedding = EXCLUDED.embedding"
                ),
                {"mid": memory_id, "tid": tenant_id, "emb": _to_pgvector(embedding)},
            )
            await session.commit()

    async def search(self, tenant_id: str, embedding: list[float], *, limit: int) -> list[VectorHit]:
        from sqlalchemy import text

        async with self._session_factory() as session:
            rows = await session.execute(
                text(
                    "SELECT memory_id, embedding <=> :emb AS distance "
                    "FROM memory_embeddings WHERE tenant_id = :tid "
                    "ORDER BY distance ASC LIMIT :lim"
                ),
                {"emb": _to_pgvector(embedding), "tid": tenant_id, "lim": limit},
            )
            return [VectorHit(memory_id=str(r[0]), distance=float(r[1])) for r in rows]

    async def delete(self, tenant_id: str, memory_id: str) -> None:
        from sqlalchemy import text

        async with self._session_factory() as session:
            await session.execute(
                text("DELETE FROM memory_embeddings WHERE tenant_id = :tid AND memory_id = :mid"),
                {"tid": tenant_id, "mid": memory_id},
            )
            await session.commit()


def _cosine_distance(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 1.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 1.0
    return 1.0 - (dot / (na * nb))


def _to_pgvector(embedding: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in embedding) + "]"

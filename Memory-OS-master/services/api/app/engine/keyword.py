"""Keyword-search backend abstraction.

OpenSearch is used when configured; otherwise the deterministic in-process
BM25-lite backend (engine/retrieval.py) serves the same interface. The retrieval
pipeline depends only on this interface, so the backend can change without
touching ranking or fusion.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.config import get_settings
from app.engine.retrieval import BM25Lite, KeywordDoc, tokenize


class KeywordBackend(ABC):
    @abstractmethod
    async def index(self, tenant_id: str, memory_id: str, content: str) -> None: ...

    @abstractmethod
    async def search(self, tenant_id: str, query: str, *, limit: int) -> list[tuple[str, float]]: ...

    @abstractmethod
    async def delete(self, tenant_id: str, memory_id: str) -> None: ...


class BM25LiteBackend(KeywordBackend):
    """In-process fallback. The retrieval service currently builds a per-query
    corpus for exact tenant scoping; this backend also supports an incremental
    index for parity with OpenSearch semantics."""

    def __init__(self) -> None:
        self._docs: dict[str, dict[str, list[str]]] = {}

    async def index(self, tenant_id: str, memory_id: str, content: str) -> None:
        self._docs.setdefault(tenant_id, {})[memory_id] = tokenize(content)

    async def search(self, tenant_id: str, query: str, *, limit: int) -> list[tuple[str, float]]:
        bucket = self._docs.get(tenant_id, {})
        docs = [KeywordDoc(memory_id=mid, tokens=toks) for mid, toks in bucket.items()]
        return BM25Lite(docs).search(query, limit=limit)

    async def delete(self, tenant_id: str, memory_id: str) -> None:
        bucket = self._docs.get(tenant_id, {})
        bucket.pop(memory_id, None)


class OpenSearchBackend(KeywordBackend):
    """OpenSearch implementation. Index name is namespaced per tenant to guarantee
    isolation. Requires opensearch-py and OPENSEARCH_URL."""

    def __init__(self, url: str) -> None:
        from opensearchpy import AsyncOpenSearch  # lazy import

        self._client = AsyncOpenSearch(hosts=[url])

    def _index_name(self, tenant_id: str) -> str:
        return f"memories-{tenant_id}".lower()

    async def index(self, tenant_id: str, memory_id: str, content: str) -> None:
        await self._client.index(
            index=self._index_name(tenant_id), id=memory_id,
            body={"content": content}, refresh=True,
        )

    async def search(self, tenant_id: str, query: str, *, limit: int) -> list[tuple[str, float]]:
        res = await self._client.search(
            index=self._index_name(tenant_id),
            body={"size": limit, "query": {"match": {"content": query}}},
        )
        return [(h["_id"], float(h["_score"])) for h in res["hits"]["hits"]]

    async def delete(self, tenant_id: str, memory_id: str) -> None:
        try:
            await self._client.delete(index=self._index_name(tenant_id), id=memory_id, ignore=[404])
        except Exception:
            pass


_BACKEND: KeywordBackend | None = None


def build_keyword_backend() -> KeywordBackend:
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND
    s = get_settings()
    if s.opensearch_url:
        try:
            _BACKEND = OpenSearchBackend(s.opensearch_url)
            return _BACKEND
        except Exception:
            pass
    _BACKEND = BM25LiteBackend()
    return _BACKEND

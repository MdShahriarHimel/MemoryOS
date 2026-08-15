"""Memory service: the application core.

Enforces tenant isolation on every query, coordinates the deterministic engines,
and maintains version history. This is the single place where storage, vector
search, keyword search and ranking are composed.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import EmbeddingRequiredError, NotFoundError
from app.engine.lifecycle import LifecycleState, derive_state
from app.engine.quality import QualitySignals, compute_quality
from app.engine.ranking import Candidate, fuse_and_rank, RankedResult
from app.engine.reranker import RerankInput, rerank as rerank_candidates
from app.engine.retrieval import BM25Lite, KeywordDoc, RetrievalTrace, Stopwatch, tokenize
from app.engine.vectorstore import InMemoryVectorStore, PgVectorStore, VectorStore
from app.models import Memory, MemoryEmbedding, MemoryProvenance, MemoryVersion
from app.schemas import MemoryCreate, MemoryOut, QualityOut, SearchMode
from app.service_v03 import MemoryServiceV03Mixin

settings = get_settings()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MemoryService(MemoryServiceV03Mixin):
    def __init__(self, session: AsyncSession, vector_store: VectorStore, tenant_id: str):
        self.db = session
        self.vs = vector_store
        self.tenant_id = tenant_id  # every query is scoped to this

    # ---- quality ----------------------------------------------------------
    async def _quality_for(self, m: Memory) -> QualityOut:
        conflicts = 0  # counted lazily; kept simple in the core slice
        # Provenance is always created alongside a memory (see create()), so we
        # treat it as present rather than triggering a lazy relationship load
        # inside the async context.
        b = compute_quality(
            QualitySignals(
                confidence=m.confidence,
                reliability=m.reliability,
                observed_at=m.observed_at or m.created_at,
                access_count=m.access_count,
                has_provenance=True,
                conflict_count=conflicts,
            )
        )
        return QualityOut(**b.__dict__)

    async def _to_out(self, m: Memory, *, with_quality: bool = True) -> MemoryOut:
        return MemoryOut(
            id=m.id,
            content=m.content,
            memory_type=m.memory_type,
            importance=m.importance,
            confidence=m.confidence,
            reliability=m.reliability,
            status=m.status,
            version=m.version,
            source=m.source,
            metadata=m.meta or {},
            created_at=m.created_at,
            updated_at=m.updated_at,
            last_accessed_at=m.last_accessed_at,
            quality=(await self._quality_for(m)) if with_quality else None,
        )

    # ---- writes -----------------------------------------------------------
    async def create(self, payload: MemoryCreate) -> MemoryOut:
        return await self.create_v03(payload)

    async def get(self, memory_id: str) -> Memory:
        stmt = select(Memory).where(
            Memory.id == memory_id, Memory.tenant_id == self.tenant_id
        )
        m = (await self.db.execute(stmt)).scalar_one_or_none()
        if m is None:
            raise NotFoundError("Memory was not found.", details={"id": memory_id})
        return m

    async def get_out(self, memory_id: str) -> MemoryOut:
        m = await self.get(memory_id)
        m.access_count += 1
        m.last_accessed_at = _now()
        m.status = derive_state(
            current=LifecycleState(m.status),
            created_at=m.created_at,
            last_accessed_at=m.last_accessed_at,
            superseded_at=m.superseded_at,
            open_conflicts=0,
        ).value
        await self.db.commit()
        await self.db.refresh(m)
        return await self._memory_out_full(m)

    async def delete(self, memory_id: str) -> None:
        from app.engine.cascade import purge_memory

        await purge_memory(
            self.db, tenant_id=self.tenant_id, memory_id=memory_id,
            vector_store=self.vs, hard_delete=False,
        )
        await self.db.commit()

    async def list(self, *, limit: int, offset: int) -> tuple[list[MemoryOut], int]:
        base = select(Memory).where(
            Memory.tenant_id == self.tenant_id,
            Memory.status != LifecycleState.DELETED.value,
        )
        total = (
            await self.db.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = (
            await self.db.execute(
                base.order_by(Memory.created_at.desc()).limit(limit).offset(offset)
            )
        ).scalars().all()
        return [await self._to_out(m) for m in rows], int(total)

    # ---- search -----------------------------------------------------------
    async def search(
        self, *, query: str, mode: SearchMode, embedding: list[float] | None, top_k: int,
        memory_type: str | None = None, min_confidence: float | None = None,
        rerank: bool = True, max_graph_hops: int = 2, as_of=None,
        subject: str | None = None, predicate: str | None = None,
    ) -> tuple[list[tuple[MemoryOut, float, list[str], dict]], RetrievalTrace]:
        from app.engine.decay import compute_decay_score, decay_signals_from_memory
        from app.engine.graphstore import GraphEdgeDTO, GraphNodeDTO, GraphView, build_graph_store
        from app.engine.keyword import build_keyword_backend
        from app.engine.multihop import expand_graph
        from app.engine.temporal import TemporalMemory, query_as_of
        from app.db.session import SessionFactory
        from app.models import GraphEdge, GraphNode

        trace = RetrievalTrace(query=query)
        with Stopwatch() as sw:
            filters = [
                Memory.tenant_id == self.tenant_id,
                Memory.status.notin_([LifecycleState.DELETED.value]),
            ]
            if memory_type:
                filters.append(Memory.memory_type == memory_type)
            if min_confidence is not None:
                filters.append(Memory.confidence >= min_confidence)
            if subject:
                filters.append(Memory.subject == subject)
            if predicate:
                filters.append(Memory.predicate == predicate)

            rows = (
                await self.db.execute(select(Memory).where(*filters))
            ).scalars().all()

            # Temporal mode: filter to valid-at-as_of
            if mode == SearchMode.temporal and as_of is not None:
                temporal = [
                    TemporalMemory(
                        m.id, m.content, m.version, m.valid_from, m.valid_until,
                        m.observed_at, m.superseded_at, m.supersedes_memory_id, m.created_at,
                    )
                    for m in rows
                ]
                valid = {r.memory_id for r in query_as_of(temporal, as_of)}
                rows = [m for m in rows if m.id in valid]

            by_id = {m.id: m for m in rows}

            candidates: dict[str, Candidate] = {}

            # Vector channel
            if mode in (SearchMode.hybrid, SearchMode.vector, SearchMode.graph) and embedding is not None:
                if len(embedding) != settings.embedding_dim:
                    raise EmbeddingRequiredError(
                        "Embedding dimension mismatch.",
                        details={"expected": settings.embedding_dim, "got": len(embedding)},
                    )
                hits = await self.vs.search(self.tenant_id, embedding, limit=max(top_k * 4, 20))
                trace.vector_candidates = len(hits)
                for rank, h in enumerate(hits):
                    if h.memory_id in by_id:
                        candidates.setdefault(h.memory_id, Candidate(memory_id=h.memory_id)).channels["vector"] = rank

            # Keyword channel (OpenSearch when configured, else per-query BM25 corpus)
            if mode in (SearchMode.hybrid, SearchMode.keyword, SearchMode.graph):
                from app.core.config import get_settings
                from app.engine.retrieval import BM25Lite, KeywordDoc, tokenize

                s = get_settings()
                if s.opensearch_url:
                    kw_backend = build_keyword_backend()
                    kw = await kw_backend.search(self.tenant_id, query, limit=max(top_k * 4, 20))
                else:
                    docs = [KeywordDoc(memory_id=m.id, tokens=tokenize(m.content)) for m in rows]
                    kw = BM25Lite(docs).search(query, limit=max(top_k * 4, 20))
                trace.keyword_candidates = len(kw)
                for rank, (mid, _score) in enumerate(kw):
                    if mid in by_id:
                        candidates.setdefault(mid, Candidate(memory_id=mid)).channels["keyword"] = rank

            # Graph channel — relational edges + optional Neo4j neighborhood
            if mode in (SearchMode.hybrid, SearchMode.graph) and max_graph_hops > 0:
                graph_store = build_graph_store(SessionFactory)
                gv = await graph_store.neighborhood(self.tenant_id, depth=max_graph_hops, limit=200)
                nodes = (
                    await self.db.execute(
                        select(GraphNode).where(GraphNode.tenant_id == self.tenant_id).limit(100)
                    )
                ).scalars().all()
                edges = (
                    await self.db.execute(
                        select(GraphEdge).where(GraphEdge.tenant_id == self.tenant_id).limit(300)
                    )
                ).scalars().all()
                if gv.nodes or nodes:
                    if not gv.nodes and nodes:
                        gv = GraphView(
                            nodes=[GraphNodeDTO(n.id, n.key, n.entity_type, n.label) for n in nodes],
                            edges=[GraphEdgeDTO(e.source_id, e.target_id, e.rel_type, e.confidence) for e in edges],
                        )
                    seed_ids = list(candidates.keys())[:5] if candidates else []
                    traversal = expand_graph(gv, seed_memory_ids=seed_ids, max_hops=max_graph_hops)
                    trace.graph_candidates = len(traversal.memory_ids)
                    for rank, mid in enumerate(traversal.memory_ids):
                        if mid in by_id:
                            candidates.setdefault(mid, Candidate(memory_id=mid)).channels["graph"] = rank
                    # Also match graph nodes by query token overlap
                    q_tokens = set(tokenize(query))
                    for n in nodes:
                        if q_tokens & set(tokenize(n.label)):
                            for e in edges:
                                if e.source_memory_id and e.source_memory_id in by_id:
                                    mid = e.source_memory_id
                                    candidates.setdefault(mid, Candidate(memory_id=mid)).channels["graph"] = 0

            # Attach quality/importance/decay for boosting
            for mid, cand in candidates.items():
                m = by_id[mid]
                q = compute_quality(
                    QualitySignals(
                        confidence=m.confidence, reliability=m.reliability,
                        observed_at=m.observed_at or m.created_at,
                        access_count=m.access_count,
                        has_provenance=True, conflict_count=0,
                    )
                )
                cand.quality = q.score
                cand.importance = m.importance
                decay = compute_decay_score(decay_signals_from_memory(
                    importance=m.importance, confidence=m.confidence,
                    access_count=m.access_count, memory_type=m.memory_type,
                    created_at=m.created_at, last_accessed_at=m.last_accessed_at,
                    superseded_at=m.superseded_at,
                    contradiction_status=m.contradiction_status or "none",
                    metadata=m.meta,
                ))
                cand.quality = cand.quality * decay

            trace.merged_candidates = len(candidates)
            ranked: list[RankedResult] = fuse_and_rank(list(candidates.values()), top_k=top_k * 2 if rerank else top_k)

            if rerank and ranked:
                rerank_inputs = []
                for r in ranked:
                    m = by_id[r.memory_id]
                    cand = candidates[r.memory_id]
                    rerank_inputs.append(
                        RerankInput(
                            memory_id=r.memory_id,
                            content=m.content,
                            base=r,
                            observed_at=m.observed_at,
                            created_at=m.created_at,
                            quality=cand.quality,
                            importance=cand.importance,
                        )
                    )
                reranked = rerank_candidates(query, rerank_inputs, top_k=top_k)
                ranked = [
                    RankedResult(
                        memory_id=rr.memory_id,
                        score=rr.score,
                        channels=rr.channels,
                        explanation=rr.explanation,
                    )
                    for rr in reranked
                ]
            else:
                ranked = ranked[:top_k]

            trace.final_results = len(ranked)

        trace.latency_ms = sw.elapsed_ms

        try:
            from app.telemetry.metrics import MEMORY_SEARCHES, RETRIEVAL_LATENCY, _AVAILABLE

            if _AVAILABLE:
                MEMORY_SEARCHES.labels(self.tenant_id).inc()
                RETRIEVAL_LATENCY.labels(mode.value).observe(sw.elapsed_ms / 1000.0)
        except Exception:
            pass

        from app.models import AnalyticsEvent
        self.db.add(
            AnalyticsEvent(
                tenant_id=self.tenant_id, kind="retrieval", value=1.0,
                meta={"latency_ms": trace.latency_ms, "final": trace.final_results, "mode": mode.value},
            )
        )
        await self.db.commit()

        out: list[tuple[MemoryOut, float, list[str], dict]] = []
        for r in ranked:
            m = by_id[r.memory_id]
            out.append((await self._memory_out_full(m), r.score, r.channels, r.explanation))
        return out, trace


def build_vector_store(session_factory) -> VectorStore:
    if get_settings().is_postgres:
        return PgVectorStore(session_factory)
    return InMemoryVectorStore()

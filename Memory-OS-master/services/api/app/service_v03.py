"""v0.3 memory service extensions — temporal truth, extraction, context, benchmarks."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import EmbeddingRequiredError, NotFoundError
from app.engine.benchmark import run_memorybench
from app.engine.decay import compute_decay_score, decay_signals_from_memory
from app.engine.extraction import extract_from_content
from app.engine.lifecycle import LifecycleState
from app.engine.multihop import expand_graph
from app.engine.temporal import TemporalMemory, build_lineage, query_as_of
from app.engine.truth import (
    CanonicalMemory,
    resolve_all_current_truths,
    resolve_current_truth,
    resolve_historical_truth,
)
from app.models import (
    AnalyticsEvent,
    BenchmarkRun,
    GraphEdge,
    GraphNode,
    Memory,
    MemoryConflict,
    MemoryEmbedding,
    MemoryProvenance,
    MemoryVersion,
)
from app.schemas import (
    AsOfResponse,
    BenchmarkRunOut,
    ContextBuildResponse,
    MemoryCreate,
    MemoryDeleteResponse,
    MemoryExtractRequest,
    MemoryExtractResponse,
    MemoryOut,
    MemoryType,
    MemoryUpdate,
    ProvenanceOut,
    ExtractedFactOut,
    TimelineEntry,
    TimelineResponse,
    TruthStateOut,
)

settings = get_settings()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _truth_out(t) -> TruthStateOut:
    return TruthStateOut(
        subject=t.subject, predicate=t.predicate,
        current_value=t.current_value, current_memory_id=t.current_memory_id,
        confidence=t.confidence, lineage=t.lineage,
        is_current=t.is_current, as_of=t.as_of, reason=t.reason,
    )


def _to_canonical(m: Memory) -> CanonicalMemory:
    return CanonicalMemory(
        memory_id=m.id,
        subject=m.subject,
        predicate=m.predicate,
        object_value=m.object_value,
        content=m.content,
        version=m.version,
        confidence=m.confidence,
        valid_from=m.valid_from,
        valid_until=m.valid_until,
        observed_at=m.observed_at,
        superseded_at=m.superseded_at,
        supersedes_id=m.supersedes_memory_id,
        superseded_by_id=m.superseded_by_memory_id,
        created_at=m.created_at,
        status=m.status,
    )


async def _load_canonical_memories(db: AsyncSession, tenant_id: str) -> list[CanonicalMemory]:
    rows = (
        await db.execute(
            select(Memory).where(
                Memory.tenant_id == tenant_id,
                Memory.status.notin_([LifecycleState.DELETED.value]),
            )
        )
    ).scalars().all()
    return [_to_canonical(m) for m in rows]


async def apply_supersede(
    db: AsyncSession,
    tenant_id: str,
    old_memory: Memory,
    new_memory: Memory,
    *,
    now: datetime | None = None,
) -> None:
    """Link old → new in supersession chain without deleting history."""
    now = now or _now()
    supersede_at = new_memory.valid_from or new_memory.observed_at or now
    old_memory.superseded_at = supersede_at
    old_memory.superseded_by_memory_id = new_memory.id
    old_memory.status = LifecycleState.SUPERSEDED.value
    new_memory.supersedes_memory_id = old_memory.id
    if new_memory.valid_from is None:
        new_memory.valid_from = supersede_at
    old_memory.valid_until = supersede_at

    # Update provenance
    old_prov = (
        await db.execute(
            select(MemoryProvenance).where(MemoryProvenance.memory_id == old_memory.id)
        )
    ).scalar_one_or_none()
    if old_prov:
        refs = list(old_prov.supersedes_refs or [])
        if new_memory.id not in refs:
            refs.append(new_memory.id)
        old_prov.supersedes_refs = refs


class MemoryServiceV03Mixin:
    """Mixin methods for v0.3 — mixed into MemoryService."""

    db: AsyncSession
    tenant_id: str
    vs: object

    async def _memory_out_full(self, m: Memory, *, with_quality: bool = True) -> MemoryOut:
        quality = await self._quality_for(m) if with_quality else None  # type: ignore[attr-defined]
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
            quality=quality,
            subject=m.subject,
            predicate=m.predicate,
            object_value=m.object_value,
            normalized_content=m.normalized_content,
            valid_from=m.valid_from,
            valid_until=m.valid_until,
            observed_at=m.observed_at,
            superseded_at=m.superseded_at,
            supersedes_memory_id=m.supersedes_memory_id,
            superseded_by_memory_id=m.superseded_by_memory_id,
            contradiction_status=m.contradiction_status or "none",
            decay_score=m.decay_score if m.decay_score is not None else 1.0,
            access_count=m.access_count,
        )

    async def _update_decay(self, m: Memory) -> None:
        signals = decay_signals_from_memory(
            importance=m.importance,
            confidence=m.confidence,
            access_count=m.access_count,
            memory_type=m.memory_type,
            created_at=m.created_at,
            last_accessed_at=m.last_accessed_at,
            superseded_at=m.superseded_at,
            contradiction_status=m.contradiction_status or "none",
            metadata=m.meta,
        )
        m.decay_score = compute_decay_score(signals)

    async def create_v03(self, payload: MemoryCreate) -> MemoryOut:
        """Extended create with canonical fields and supersession."""
        now = _now()
        m = Memory(
            tenant_id=self.tenant_id,
            content=payload.content,
            memory_type=payload.memory_type.value,
            meta=payload.metadata,
            importance=payload.importance,
            confidence=payload.confidence,
            reliability=payload.reliability,
            source=payload.source,
            source_id=payload.source_id,
            user_id=payload.user_id,
            agent_id=payload.agent_id,
            session_id=payload.session_id,
            project_id=payload.project_id,
            observed_at=payload.observed_at or now,
            valid_from=payload.valid_from or payload.observed_at or now,
            valid_until=payload.valid_until,
            subject=payload.subject,
            predicate=payload.predicate,
            object_value=payload.object_value,
            normalized_content=payload.normalized_content,
            status=LifecycleState.NEW.value,
        )
        self.db.add(m)
        await self.db.flush()
        await self._update_decay(m)

        # Handle supersession
        for supersede_id in payload.supersedes:
            old = (
                await self.db.execute(
                    select(Memory).where(
                        Memory.id == supersede_id, Memory.tenant_id == self.tenant_id
                    )
                )
            ).scalar_one_or_none()
            if old:
                await apply_supersede(self.db, self.tenant_id, old, m, now=now)

        self.db.add(
            MemoryProvenance(
                memory_id=m.id,
                tenant_id=self.tenant_id,
                source_type=payload.source or "api",
                source_id=payload.source_id,
                created_by=payload.agent_id or payload.user_id or "api",
                evidence={"origin": "memory.create"},
                derived_from=list(payload.derived_from),
                supersedes_refs=list(payload.supersedes),
                observed_at=payload.observed_at or now,
            )
        )
        self.db.add(
            MemoryVersion(
                memory_id=m.id, tenant_id=self.tenant_id, version=1,
                content=m.content,
                snapshot={"confidence": m.confidence, "subject": m.subject, "predicate": m.predicate},
            )
        )

        if payload.embedding is not None:
            if len(payload.embedding) != settings.embedding_dim:
                raise EmbeddingRequiredError(
                    "Embedding dimension mismatch.",
                    details={"expected": settings.embedding_dim, "got": len(payload.embedding)},
                )
            self.db.add(
                MemoryEmbedding(memory_id=m.id, tenant_id=self.tenant_id, embedding=payload.embedding)
            )
            await self.vs.upsert(self.tenant_id, m.id, payload.embedding)  # type: ignore[attr-defined]

        from app.engine.keyword import build_keyword_backend

        await build_keyword_backend().index(self.tenant_id, m.id, m.content)

        try:
            from app.telemetry.metrics import MEMORY_WRITES, _AVAILABLE

            if _AVAILABLE:
                MEMORY_WRITES.labels(self.tenant_id).inc()
        except Exception:
            pass

        self.db.add(AnalyticsEvent(tenant_id=self.tenant_id, kind="memory.created", value=1.0))
        await self.db.commit()
        await self.db.refresh(m)

        if m.subject and m.predicate:
            from app.worker_dispatch import dispatch_sync_graph

            dispatch_sync_graph(
                self.tenant_id,
                [{
                    "source": m.subject,
                    "target": m.object_value or m.content[:80],
                    "rel_type": m.predicate,
                    "confidence": m.confidence,
                    "source_memory_id": m.id,
                }],
            )

        return await self._memory_out_full(m)

    async def update(self, memory_id: str, payload: MemoryUpdate) -> MemoryOut:
        m = await self.get(memory_id)  # type: ignore[attr-defined]
        now = _now()

        if payload.supersede and payload.content:
            # Create new version that supersedes current
            try:
                mt = MemoryType(m.memory_type)
            except ValueError:
                mt = MemoryType.observation
            new_payload = MemoryCreate(
                content=payload.content,
                memory_type=mt,
                embedding=payload.embedding,
                metadata=payload.metadata or m.meta,
                importance=payload.importance if payload.importance is not None else m.importance,
                confidence=payload.confidence if payload.confidence is not None else m.confidence,
                reliability=payload.reliability if payload.reliability is not None else m.reliability,
                source=m.source,
                source_id=m.source_id,
                subject=payload.subject or m.subject,
                predicate=payload.predicate or m.predicate,
                object_value=payload.object_value or m.object_value,
                supersedes=[memory_id],
                derived_from=[memory_id],
            )
            return await self.create_v03(new_payload)

        if payload.content is not None:
            if payload.preserve_history:
                self.db.add(
                    MemoryVersion(
                        memory_id=m.id, tenant_id=self.tenant_id,
                        version=m.version, content=m.content,
                        snapshot={"confidence": m.confidence},
                    )
                )
                m.version += 1
            m.content = payload.content
        if payload.metadata is not None:
            m.meta = payload.metadata
        if payload.importance is not None:
            m.importance = payload.importance
        if payload.confidence is not None:
            m.confidence = payload.confidence
        if payload.reliability is not None:
            m.reliability = payload.reliability
        if payload.status is not None:
            m.status = payload.status
        if payload.subject is not None:
            m.subject = payload.subject
        if payload.predicate is not None:
            m.predicate = payload.predicate
        if payload.object_value is not None:
            m.object_value = payload.object_value

        m.updated_at = now
        await self._update_decay(m)

        if payload.embedding is not None:
            emb = (
                await self.db.execute(
                    select(MemoryEmbedding).where(MemoryEmbedding.memory_id == memory_id)
                )
            ).scalar_one_or_none()
            if emb:
                emb.embedding = payload.embedding
            else:
                self.db.add(
                    MemoryEmbedding(memory_id=memory_id, tenant_id=self.tenant_id, embedding=payload.embedding)
                )
            await self.vs.upsert(self.tenant_id, memory_id, payload.embedding)  # type: ignore[attr-defined]

        self.db.add(AnalyticsEvent(tenant_id=self.tenant_id, kind="memory.updated", value=1.0))
        await self.db.commit()
        await self.db.refresh(m)
        return await self._memory_out_full(m)

    async def extract(self, req: MemoryExtractRequest) -> MemoryExtractResponse:
        result = extract_from_content(
            req.content,
            source_type=req.source.type,
            structured_facts=req.structured_facts,
        )
        facts_out = [
            ExtractedFactOut(
                subject=f.subject, predicate=f.predicate, value=f.value,
                memory_type=f.memory_type, confidence=f.confidence,
                polarity=f.polarity, temporal_state=f.temporal_state,
                valid_from=f.valid_from, supersedes=f.supersedes, content=f.content,
            )
            for f in result.facts
        ]
        stored_ids: list[str] = []
        if req.store:
            for f in result.facts:
                try:
                    mt = MemoryType(f.memory_type)
                except ValueError:
                    mt = MemoryType.observation
                created = await self.create_v03(
                    MemoryCreate(
                        content=f.content or req.content,
                        memory_type=mt,
                        confidence=f.confidence,
                        source=req.source.type,
                        source_id=req.source.id,
                        subject=f.subject,
                        predicate=f.predicate,
                        object_value=f.value,
                        normalized_content=f.normalized_content,
                        valid_from=f.valid_from,
                        supersedes=f.supersedes,
                        embedding=req.embedding,
                    )
                )
                stored_ids.append(created.id)
        return MemoryExtractResponse(facts=facts_out, method=result.method, stored_memory_ids=stored_ids)

    async def get_provenance(self, memory_id: str) -> ProvenanceOut:
        m = await self.get(memory_id)  # type: ignore[attr-defined]
        prov = (
            await self.db.execute(
                select(MemoryProvenance).where(MemoryProvenance.memory_id == memory_id)
            )
        ).scalar_one_or_none()
        if prov is None:
            return ProvenanceOut(
                memory_id=memory_id,
                source_type=m.source,
                source_id=m.source_id,
                observed_at=m.observed_at,
                created_at=m.created_at,
            )
        evidence = prov.evidence if isinstance(prov.evidence, list) else [prov.evidence]
        return ProvenanceOut(
            memory_id=memory_id,
            source_type=prov.source_type,
            source_id=prov.source_id,
            created_by=prov.created_by,
            observed_at=prov.observed_at or m.observed_at,
            extracted_at=prov.extracted_at,
            created_at=m.created_at,
            derived_from=list(prov.derived_from or []),
            supersedes=list(prov.supersedes_refs or []),
            evidence=evidence,
            confidence=prov.extraction_confidence or m.confidence,
        )

    async def get_timeline(self, memory_id: str) -> TimelineResponse:
        m = await self.get(memory_id)  # type: ignore[attr-defined]
        canonical = await _load_canonical_memories(self.db, self.tenant_id)
        chains = build_lineage([
            TemporalMemory(
                c.memory_id, c.content, c.version, c.valid_from, c.valid_until,
                c.observed_at, c.superseded_at, c.supersedes_id, c.created_at,
            )
            for c in canonical
        ])
        chain_ids: list[str] = [memory_id]
        for chain in chains:
            if memory_id in chain:
                chain_ids = chain
                break

        entries: list[TimelineEntry] = []
        current_id = None
        for mid in chain_ids:
            mem = next((c for c in canonical if c.memory_id == mid), None)
            if mem is None:
                continue
            is_current = mem.superseded_at is None and mem.superseded_by_id is None
            if is_current:
                current_id = mid
            entries.append(
                TimelineEntry(
                    memory_id=mid,
                    content=mem.content,
                    version=mem.version,
                    valid_from=mem.valid_from,
                    valid_until=mem.valid_until,
                    observed_at=mem.observed_at,
                    superseded_at=mem.superseded_at,
                    status=mem.status,
                    is_current=is_current,
                )
            )

        current_truth = None
        if m.subject and m.predicate:
            truth = resolve_current_truth(canonical, m.subject, m.predicate)
            current_truth = _truth_out(truth)

        return TimelineResponse(memory_id=memory_id, chain=entries, current_truth=current_truth)

    async def query_as_of(self, as_of: datetime, *, subject: str | None = None, predicate: str | None = None) -> AsOfResponse:
        canonical = await _load_canonical_memories(self.db, self.tenant_id)
        truths: list[TruthStateOut] = []

        if subject and predicate:
            t = resolve_historical_truth(canonical, subject, predicate, as_of)
            truths.append(_truth_out(t))
        else:
            pairs = {(c.subject, c.predicate) for c in canonical if c.subject and c.predicate}
            for subj, pred in sorted(pairs):
                if subj and pred:
                    t = resolve_historical_truth(canonical, subj, pred, as_of)
                    if t.current_value:
                        truths.append(_truth_out(t))

        temporal = [
            TemporalMemory(
                c.memory_id, c.content, c.version, c.valid_from, c.valid_until,
                c.observed_at, c.superseded_at, c.supersedes_id, c.created_at,
            )
            for c in canonical
        ]
        valid_results = query_as_of(temporal, as_of)
        memories: list[MemoryOut] = []
        for vr in valid_results[:50]:
            m = await self.get(vr.memory_id)  # type: ignore[attr-defined]
            memories.append(await self._memory_out_full(m))

        return AsOfResponse(as_of=as_of, truths=truths, memories=memories)

    async def build_context_v2(
        self, *, query: str, embedding: list[float] | None = None,
        user_id: str | None = None, agent_id: str | None = None,
        max_tokens: int = 4000, top_k: int = 12,
    ) -> ContextBuildResponse:
        from app.engine.conflicts import MemoryConflictInput, analyze_conflicts
        from app.engine.retrieval import tokenize
        from app.engine.graphstore import GraphView, GraphNodeDTO, GraphEdgeDTO
        from app.schemas import SearchMode

        results, trace = await self.search(  # type: ignore[attr-defined]
            query=query, mode=SearchMode.hybrid, embedding=embedding, top_k=top_k,
            max_graph_hops=2,
        )
        memories = [m for (m, *_rest) in results]

        # Recent memories
        recent_rows = (
            await self.db.execute(
                select(Memory).where(
                    Memory.tenant_id == self.tenant_id,
                    Memory.status.notin_([LifecycleState.DELETED.value, LifecycleState.SUPERSEDED.value]),
                ).order_by(Memory.created_at.desc()).limit(5)
            )
        ).scalars().all()
        recent = [await self._memory_out_full(m) for m in recent_rows]
        seen = {m.id for m in memories}
        for r in recent:
            if r.id not in seen:
                memories.append(r)

        # Current truths
        canonical = await _load_canonical_memories(self.db, self.tenant_id)
        truths = [_truth_out(t) for t in resolve_all_current_truths(canonical) if t.current_value]

        # Graph entities/relationships
        nodes = (
            await self.db.execute(
                select(GraphNode).where(GraphNode.tenant_id == self.tenant_id).limit(50)
            )
        ).scalars().all()
        edges = (
            await self.db.execute(
                select(GraphEdge).where(GraphEdge.tenant_id == self.tenant_id).limit(100)
            )
        ).scalars().all()
        entities = [{"id": n.id, "key": n.key, "type": n.entity_type, "label": n.label} for n in nodes]
        relationships = [
            {"source": e.source_id, "target": e.target_id, "type": e.rel_type, "confidence": e.confidence}
            for e in edges
        ]

        # Multi-hop expansion from retrieved memories
        if memories:
            gv = GraphView(
                nodes=[GraphNodeDTO(n.id, n.key, n.entity_type, n.label) for n in nodes],
                edges=[GraphEdgeDTO(e.source_id, e.target_id, e.rel_type, e.confidence) for e in edges],
            )
            traversal = expand_graph(gv, seed_memory_ids=[m.id for m in memories[:5]], max_hops=2)

        # Timeline from retrieved memories with subject+predicate
        timeline: list[dict] = []
        for mem in memories[:5]:
            if mem.subject and mem.predicate:
                tl = await self.get_timeline(mem.id)
                timeline.append({"memory_id": mem.id, "chain": [e.model_dump() for e in tl.chain]})

        # Conflicts among retrieved
        conflict_rows = (
            await self.db.execute(
                select(Memory).where(Memory.tenant_id == self.tenant_id).limit(200)
            )
        ).scalars().all()
        conflicts_raw = analyze_conflicts([
            MemoryConflictInput(m.id, m.content, m.valid_from, m.valid_until)
            for m in conflict_rows
        ])
        retrieved_ids = {m.id for m in memories}
        conflicts = [
            {"memory_a": c.memory_a, "memory_b": c.memory_b, "reason": c.reason, "severity": c.severity}
            for c in conflicts_raw
            if c.memory_a in retrieved_ids or c.memory_b in retrieved_ids
        ]

        # Full provenance
        provenance = []
        for mem in memories:
            prov = await self.get_provenance(mem.id)
            provenance.append(prov.model_dump())

        from app.engine.context_budget import estimate_tokens, pack_by_token_budget

        pack_items = [(m.id, m.content) for m in memories]
        pack_items.extend((f"truth:{i}", str(t)) for i, t in enumerate(truths))
        kept_ids, tokens_used, truncated = pack_by_token_budget(pack_items, max_tokens=max_tokens)
        kept = {k for k in kept_ids if not k.startswith("truth:")}
        memories = [m for m in memories if m.id in kept]

        return ContextBuildResponse(
            query=query,
            memories=memories,
            current_truths=[t.model_dump() for t in truths],
            entities=entities,
            relationships=relationships,
            timeline=timeline,
            conflicts=conflicts,
            provenance=provenance,
            retrieval_trace=trace.as_dict(),
            max_tokens=max_tokens,
            tokens_used=tokens_used,
            truncated=truncated,
        )

    async def export_memories(self, *, user_id: str | None = None) -> dict:
        filters = [Memory.tenant_id == self.tenant_id, Memory.status != LifecycleState.DELETED.value]
        if user_id:
            filters.append(Memory.user_id == user_id)
        rows = (await self.db.execute(select(Memory).where(*filters))).scalars().all()
        items = [await self._memory_out_full(m) for m in rows]
        return {"count": len(items), "memories": [i.model_dump(mode="json") for i in items]}

    async def delete_data(
        self, *, user_id: str | None = None, hard_delete: bool = False, verify: bool = False,
    ) -> MemoryDeleteResponse:
        from app.engine.cascade import purge_tenant_memories

        count, stores, failed = await purge_tenant_memories(
            self.db,
            tenant_id=self.tenant_id,
            vector_store=self.vs,
            user_id=user_id,
            hard_delete=hard_delete,
        )
        await self.db.commit()

        verified = False
        if verify:
            filters = [Memory.tenant_id == self.tenant_id]
            if user_id:
                filters.append(Memory.user_id == user_id)
            remaining = (
                await self.db.execute(
                    select(func.count()).select_from(Memory).where(
                        *filters, Memory.status != LifecycleState.DELETED.value
                    )
                )
            ).scalar_one()
            verified = remaining == 0

        return MemoryDeleteResponse(
            deleted_count=count,
            verified=verified,
            stores_cleaned=stores,
            stores_failed=failed,
        )

    async def run_benchmark(self, *, name: str, categories: list[str] | None, scale: int) -> BenchmarkRunOut:
        run = BenchmarkRun(
            id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            name=name,
            status="running",
            config={"categories": categories, "scale": scale},
        )
        self.db.add(run)
        await self.db.commit()

        bench = run_memorybench(categories=categories, scale=scale)
        run.status = "completed"
        run.completed_at = _now()
        run.results = {
            "total_passed": bench.total_passed,
            "total_failed": bench.total_failed,
            "duration_ms": bench.duration_ms,
            "scale": bench.scale,
            "categories": [
                {"category": c.category, "passed": c.passed, "failed": c.failed, "details": c.details}
                for c in bench.categories
            ],
            "retrieval_summary": {
                "mean_mrr": bench.retrieval_summary.mean_mrr if bench.retrieval_summary else 0,
                "mean_recall_at_5": bench.retrieval_summary.mean_recall_at_k.get(5, 0) if bench.retrieval_summary else 0,
            },
            "notes": bench.notes,
        }
        await self.db.commit()
        await self.db.refresh(run)
        return BenchmarkRunOut(
            id=run.id, name=run.name, status=run.status,
            config=run.config, results=run.results,
            created_at=run.created_at, completed_at=run.completed_at,
        )

    async def get_benchmark(self, run_id: str) -> BenchmarkRunOut:
        run = (
            await self.db.execute(
                select(BenchmarkRun).where(
                    BenchmarkRun.id == run_id, BenchmarkRun.tenant_id == self.tenant_id
                )
            )
        ).scalar_one_or_none()
        if run is None:
            raise NotFoundError("Benchmark run not found.", details={"id": run_id})
        return BenchmarkRunOut(
            id=run.id, name=run.name, status=run.status,
            config=run.config, results=run.results,
            created_at=run.created_at, completed_at=run.completed_at,
        )

    async def list_benchmarks(self) -> list[BenchmarkRunOut]:
        rows = (
            await self.db.execute(
                select(BenchmarkRun).where(BenchmarkRun.tenant_id == self.tenant_id)
                .order_by(BenchmarkRun.created_at.desc()).limit(50)
            )
        ).scalars().all()
        return [
            BenchmarkRunOut(
                id=r.id, name=r.name, status=r.status,
                config=r.config, results=r.results,
                created_at=r.created_at, completed_at=r.completed_at,
            )
            for r in rows
        ]

"""Memory, search, context-builder, extraction, temporal, and provenance endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.api.deps import (
    get_memory_service_read,
    get_memory_service_write,
    get_principal,
    Principal,
    require_quota,
)
from app.api.idempotency import record_idempotent
from app.db.session import get_session
from app.service_sessions import record_event
from app.schemas import (
    AsOfRequest,
    AsOfResponse,
    BenchmarkRunOut,
    BenchmarkRunRequest,
    ContextBuildRequest,
    ContextBuildResponse,
    MemoryCreate,
    MemoryDeleteRequest,
    MemoryDeleteResponse,
    MemoryExportRequest,
    MemoryExtractRequest,
    MemoryExtractResponse,
    MemoryOut,
    MemoryUpdate,
    Page,
    ProvenanceOut,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    TimelineResponse,
)
from app.service import MemoryService
from app.engine.explanation import summarize_explanation

router = APIRouter(prefix="/v1", tags=["memory"])


@router.post("/memory", response_model=MemoryOut, status_code=201)
async def create_memory(
    payload: MemoryCreate,
    request: Request,
    svc: MemoryService = Depends(get_memory_service_write),
    principal: Principal = Depends(require_quota("memory.write")),
    db: AsyncSession = Depends(get_session),
) -> MemoryOut:
    from app.service_idempotency import body_hash_from_json, lookup_idempotent

    idem_key = request.headers.get("Idempotency-Key") or request.headers.get("X-Idempotency-Key")
    if idem_key:
        cached = await lookup_idempotent(
            db,
            tenant_id=principal.tenant_id,
            key=idem_key,
            method="POST",
            path="/v1/memory",
            body_hash=body_hash_from_json(payload.model_dump(mode="json")),
        )
        if cached is not None:
            return MemoryOut.model_validate(cached.response_body)

    out = await svc.create(payload)
    await record_event(
        db,
        principal.tenant_id,
        payload.session_id,
        event_type="memory_write",
        detail=f"Created memory {out.id[:8]}…",
    )
    if idem_key:
        await record_idempotent(
            request, principal, db, status_code=201,
            response_body=out.model_dump(mode="json"),
            body_hash=body_hash_from_json(payload.model_dump(mode="json")),
        )
    return out


@router.patch("/memory/{memory_id}", response_model=MemoryOut)
async def update_memory(
    memory_id: str,
    payload: MemoryUpdate,
    svc: MemoryService = Depends(get_memory_service_write),
) -> MemoryOut:
    return await svc.update(memory_id, payload)


@router.get("/memory", response_model=Page)
async def list_memories(
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc: MemoryService = Depends(get_memory_service_read),
) -> Page:
    items, total = await svc.list(limit=limit, offset=offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/memory/{memory_id}", response_model=MemoryOut)
async def get_memory(
    memory_id: str, svc: MemoryService = Depends(get_memory_service_read)
) -> MemoryOut:
    return await svc.get_out(memory_id)


@router.delete("/memory/{memory_id}", status_code=204, response_class=Response)
async def delete_memory(
    memory_id: str, svc: MemoryService = Depends(get_memory_service_write)
) -> Response:
    await svc.delete(memory_id)
    return Response(status_code=204)


@router.post("/memory/search", response_model=SearchResponse)
async def search_memory(
    req: SearchRequest,
    svc: MemoryService = Depends(get_memory_service_read),
    principal: Principal = Depends(require_quota("memory.search")),
    db: AsyncSession = Depends(get_session),
) -> SearchResponse:
    results, trace = await svc.search(
        query=req.query,
        mode=req.mode,
        embedding=req.embedding,
        top_k=req.top_k,
        memory_type=req.memory_type.value if req.memory_type else None,
        min_confidence=req.min_confidence,
        rerank=req.rerank,
        max_graph_hops=req.max_graph_hops,
        as_of=req.as_of,
        subject=req.subject,
        predicate=req.predicate,
    )
    await record_event(
        db,
        principal.tenant_id,
        req.session_id,
        event_type="search",
        detail=f"Search: {req.query[:120]}",
        latency_ms=trace.latency_ms,
    )
    return SearchResponse(
        results=[
            SearchResultItem(
                memory=m,
                score=s,
                channels=ch,
                explanation=ex,
                explanation_summary=summarize_explanation(ex),
            )
            for (m, s, ch, ex) in results
        ],
        retrieval_trace=trace.as_dict(),
    )


@router.post("/memory/extract", response_model=MemoryExtractResponse)
async def extract_memory(
    req: MemoryExtractRequest, svc: MemoryService = Depends(get_memory_service_write)
) -> MemoryExtractResponse:
    return await svc.extract(req)


@router.post("/memory/as-of", response_model=AsOfResponse)
async def memory_as_of(
    req: AsOfRequest, svc: MemoryService = Depends(get_memory_service_read)
) -> AsOfResponse:
    return await svc.query_as_of(req.as_of, subject=req.subject, predicate=req.predicate)


@router.get("/memory/{memory_id}/timeline", response_model=TimelineResponse)
async def memory_timeline(
    memory_id: str, svc: MemoryService = Depends(get_memory_service_read)
) -> TimelineResponse:
    return await svc.get_timeline(memory_id)


@router.get("/memory/{memory_id}/provenance", response_model=ProvenanceOut)
async def memory_provenance(
    memory_id: str, svc: MemoryService = Depends(get_memory_service_read)
) -> ProvenanceOut:
    return await svc.get_provenance(memory_id)


@router.post("/memory/export")
async def export_memories(
    req: MemoryExportRequest, svc: MemoryService = Depends(get_memory_service_write)
) -> dict:
    return await svc.export_memories(user_id=req.user_id)


@router.post("/memory/delete", response_model=MemoryDeleteResponse)
async def bulk_delete_memories(
    req: MemoryDeleteRequest, svc: MemoryService = Depends(get_memory_service_write)
) -> MemoryDeleteResponse:
    return await svc.delete_data(
        user_id=req.user_id, hard_delete=req.hard_delete, verify=req.verify
    )


@router.post("/context", response_model=ContextBuildResponse)
async def build_context(
    req: ContextBuildRequest,
    svc: MemoryService = Depends(get_memory_service_write),
    principal: Principal = Depends(require_quota("context.build")),
    db: AsyncSession = Depends(get_session),
) -> ContextBuildResponse:
    out = await svc.build_context_v2(
        query=req.query,
        embedding=req.embedding,
        user_id=req.user_id,
        agent_id=req.agent_id,
        max_tokens=req.max_tokens,
    )
    await record_event(
        db,
        principal.tenant_id,
        req.session_id,
        event_type="context",
        detail=f"Context build: {req.query[:120]}",
        latency_ms=out.retrieval_trace.get("latency_ms"),
    )
    return out


@router.post("/context/build", response_model=ContextBuildResponse)
async def build_context_legacy(
    req: ContextBuildRequest, svc: MemoryService = Depends(get_memory_service_read)
) -> ContextBuildResponse:
    """Backward-compatible alias for POST /v1/context."""
    return await svc.build_context_v2(
        query=req.query,
        embedding=req.embedding,
        user_id=req.user_id,
        agent_id=req.agent_id,
        max_tokens=req.max_tokens,
    )

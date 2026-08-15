"""Knowledge-graph endpoints backed by the graph store abstraction."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, get_principal
from app.db.session import SessionFactory, get_session
from app.engine.graphstore import build_graph_store

router = APIRouter(prefix="/v1/graph", tags=["graph"])
_graph = build_graph_store(SessionFactory)


class EdgeCreate(BaseModel):
    source: str
    target: str
    rel_type: str = "related_to"
    confidence: float = 0.5
    source_memory_id: str | None = None


@router.get("")
async def get_graph(
    depth: int = Query(1, ge=1, le=4),
    limit: int = Query(200, ge=1, le=1000),
    principal: Principal = Depends(get_principal),
):
    view = await _graph.neighborhood(principal.tenant_id, depth=depth, limit=limit)
    return {
        "nodes": [n.__dict__ for n in view.nodes],
        "edges": [e.__dict__ for e in view.edges],
    }


@router.post("/edges", status_code=201)
async def create_edge(
    req: EdgeCreate,
    principal: Principal = Depends(get_principal),
):
    await _graph.upsert_edge(
        principal.tenant_id, req.source, req.target, req.rel_type,
        confidence=req.confidence, source_memory_id=req.source_memory_id,
    )
    return {"status": "ok"}

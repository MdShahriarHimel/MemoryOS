"""Benchmark endpoints — MemoryBench and retrieval evaluation."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_memory_service, require_role
from app.schemas import BenchmarkRunOut, BenchmarkRunRequest
from app.security.rbac import Role
from app.service import MemoryService

router = APIRouter(prefix="/v1/benchmarks", tags=["benchmarks"])


@router.post("/run", response_model=BenchmarkRunOut)
async def run_benchmark(
    req: BenchmarkRunRequest,
    svc: MemoryService = Depends(get_memory_service),
    _admin=Depends(require_role(Role.developer)),
) -> BenchmarkRunOut:
    return await svc.run_benchmark(
        name=req.name, categories=req.categories, scale=req.scale
    )


@router.get("", response_model=list[BenchmarkRunOut])
async def list_benchmarks(
    svc: MemoryService = Depends(get_memory_service),
) -> list[BenchmarkRunOut]:
    return await svc.list_benchmarks()


@router.get("/{run_id}", response_model=BenchmarkRunOut)
async def get_benchmark(
    run_id: str,
    svc: MemoryService = Depends(get_memory_service),
) -> BenchmarkRunOut:
    return await svc.get_benchmark(run_id)

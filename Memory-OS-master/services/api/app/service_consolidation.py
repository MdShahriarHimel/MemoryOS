"""Apply consolidation plans produced by run_reflection.

Execution is explicit and deterministic — never auto-run. Each action type
maps to a safe, reversible-ish mutation (supersede, archive, conflict queue,
provenance backfill).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.consolidation import ConsolidationAction
from app.engine.lifecycle import FROZEN, LifecycleState
from app.models import Memory, MemoryConflict, MemoryProvenance


@dataclass
class ActionResult:
    action: str
    memory_ids: list[str]
    result: str  # applied | skipped | dry_run
    detail: str
    reason: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _get_memory(db: AsyncSession, tenant_id: str, memory_id: str) -> Memory | None:
    return (
        await db.execute(
            select(Memory).where(Memory.id == memory_id, Memory.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()


_FROZEN = {s.value for s in FROZEN}


async def _apply_merge(
    db: AsyncSession,
    tenant_id: str,
    action: ConsolidationAction,
    *,
    now: datetime,
    dry_run: bool,
) -> ActionResult:
    if len(action.memory_ids) < 2:
        return ActionResult(action.action, action.memory_ids, "skipped", "Need canonical + duplicate", action.reason)

    canonical_id = action.memory_ids[0]
    canonical = await _get_memory(db, tenant_id, canonical_id)
    if canonical is None:
        return ActionResult(action.action, action.memory_ids, "skipped", "Canonical not found", action.reason)
    if canonical.status in _FROZEN:
        return ActionResult(action.action, action.memory_ids, "skipped", "Canonical frozen", action.reason)

    merged: list[str] = []
    for dup_id in action.memory_ids[1:]:
        if dup_id == canonical_id:
            continue
        dup = await _get_memory(db, tenant_id, dup_id)
        if dup is None:
            continue
        if dup.status in _FROZEN:
            continue
        if dry_run:
            merged.append(dup_id)
            continue
        dup.superseded_at = now
        dup.superseded_by_memory_id = canonical_id
        dup.valid_until = now
        dup.status = LifecycleState.SUPERSEDED.value
        dup.updated_at = now
        merged.append(dup_id)

    if dry_run:
        return ActionResult(
            action.action, action.memory_ids, "dry_run",
            f"Would merge {len(merged)} into {canonical_id}", action.reason,
        )
    if not merged:
        return ActionResult(action.action, action.memory_ids, "skipped", "Nothing to merge", action.reason)
    return ActionResult(
        action.action, action.memory_ids, "applied",
        f"Merged {len(merged)} duplicate(s) into {canonical_id}", action.reason,
    )


async def _apply_archive(
    db: AsyncSession,
    tenant_id: str,
    action: ConsolidationAction,
    *,
    now: datetime,
    dry_run: bool,
) -> ActionResult:
    archived: list[str] = []
    for mid in action.memory_ids:
        mem = await _get_memory(db, tenant_id, mid)
        if mem is None:
            continue
        if mem.status in _FROZEN:
            continue
        if dry_run:
            archived.append(mid)
            continue
        mem.status = LifecycleState.ARCHIVED.value
        mem.updated_at = now
        archived.append(mid)

    if dry_run:
        return ActionResult(action.action, action.memory_ids, "dry_run", f"Would archive {len(archived)}", action.reason)
    if not archived:
        return ActionResult(action.action, action.memory_ids, "skipped", "Nothing to archive", action.reason)
    return ActionResult(action.action, action.memory_ids, "applied", f"Archived {len(archived)}", action.reason)


async def _apply_conflict(
    db: AsyncSession,
    tenant_id: str,
    action: ConsolidationAction,
    *,
    dry_run: bool,
) -> ActionResult:
    if len(action.memory_ids) < 2:
        return ActionResult(action.action, action.memory_ids, "skipped", "Need two memories", action.reason)
    a_id, b_id = sorted(action.memory_ids[:2])
    existing = (
        await db.execute(
            select(MemoryConflict).where(
                MemoryConflict.tenant_id == tenant_id,
                MemoryConflict.memory_a_id == a_id,
                MemoryConflict.memory_b_id == b_id,
                MemoryConflict.status == "open",
            )
        )
    ).scalar_one_or_none()
    if existing:
        return ActionResult(action.action, action.memory_ids, "skipped", "Conflict already open", action.reason)
    if dry_run:
        return ActionResult(action.action, action.memory_ids, "dry_run", "Would open conflict", action.reason)
    db.add(MemoryConflict(
        tenant_id=tenant_id,
        memory_a_id=a_id,
        memory_b_id=b_id,
        reason=action.reason[:255],
        status="open",
    ))
    return ActionResult(action.action, action.memory_ids, "applied", "Conflict queued", action.reason)


async def _apply_provenance(
    db: AsyncSession,
    tenant_id: str,
    action: ConsolidationAction,
    *,
    now: datetime,
    dry_run: bool,
) -> ActionResult:
    fixed: list[str] = []
    for mid in action.memory_ids:
        mem = await _get_memory(db, tenant_id, mid)
        if mem is None or mem.source is not None:
            continue
        if dry_run:
            fixed.append(mid)
            continue
        mem.source = "reflection_backfill"
        mem.updated_at = now
        prov = (
            await db.execute(
                select(MemoryProvenance).where(
                    MemoryProvenance.memory_id == mid,
                    MemoryProvenance.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if prov is None:
            db.add(MemoryProvenance(
                memory_id=mid,
                tenant_id=tenant_id,
                source_type="unknown",
                source_id="reflection",
            ))
        elif prov.source_type is None:
            prov.source_type = "unknown"
        fixed.append(mid)

    if dry_run:
        return ActionResult(action.action, action.memory_ids, "dry_run", f"Would fix {len(fixed)}", action.reason)
    if not fixed:
        return ActionResult(action.action, action.memory_ids, "skipped", "No provenance gaps", action.reason)
    return ActionResult(action.action, action.memory_ids, "applied", f"Fixed provenance on {len(fixed)}", action.reason)


async def execute_actions(
    db: AsyncSession,
    tenant_id: str,
    actions: list[ConsolidationAction],
    *,
    dry_run: bool = False,
    max_actions: int = 100,
    action_filter: set[str] | None = None,
) -> list[ActionResult]:
    now = _now()
    results: list[ActionResult] = []
    for action in actions[:max_actions]:
        if action_filter and action.action not in action_filter:
            continue
        if action.action == "merge":
            res = await _apply_merge(db, tenant_id, action, now=now, dry_run=dry_run)
        elif action.action == "archive":
            res = await _apply_archive(db, tenant_id, action, now=now, dry_run=dry_run)
        elif action.action == "review_conflict":
            res = await _apply_conflict(db, tenant_id, action, dry_run=dry_run)
        elif action.action == "fix_provenance":
            res = await _apply_provenance(db, tenant_id, action, now=now, dry_run=dry_run)
        else:
            res = ActionResult(action.action, action.memory_ids, "skipped", "Unknown action", action.reason)
        results.append(res)
    if not dry_run:
        await db.commit()
    return results

"""Audit log service."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def record_audit(
    session: AsyncSession,
    *,
    tenant_id: str,
    actor: str | None,
    action: str,
    target: str | None = None,
    request_id: str | None = None,
    result: str = "ok",
    details: dict | None = None,
) -> AuditLog:
    row = AuditLog(
        tenant_id=tenant_id,
        actor=actor,
        action=action,
        target=target,
        request_id=request_id,
        result=result,
        details=details or {},
    )
    session.add(row)
    return row


async def list_audit_logs(
    session: AsyncSession,
    *,
    tenant_id: str,
    limit: int = 50,
    offset: int = 0,
    action: str | None = None,
) -> tuple[list[AuditLog], int]:
    q = select(AuditLog).where(AuditLog.tenant_id == tenant_id)
    if action:
        q = q.where(AuditLog.action == action)
    total_q = select(AuditLog.id).where(AuditLog.tenant_id == tenant_id)
    if action:
        total_q = total_q.where(AuditLog.action == action)
    total = len((await session.execute(total_q)).all())
    rows = (
        await session.execute(q.order_by(AuditLog.at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return list(rows), total

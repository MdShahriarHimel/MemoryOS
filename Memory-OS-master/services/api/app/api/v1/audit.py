"""Audit log API."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, get_principal, require_role
from app.db.session import get_session
from app.security.rbac import Role
from app.service_audit import list_audit_logs

router = APIRouter(prefix="/v1/audit", tags=["audit"])


class AuditLogOut(BaseModel):
    id: str
    tenant_id: str
    actor: str | None
    action: str
    target: str | None
    request_id: str | None
    result: str
    details: dict
    at: datetime


@router.get("/logs", response_model=list[AuditLogOut])
async def get_audit_logs(
    principal: Principal = Depends(require_role(Role.admin)),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: str | None = None,
):
    rows, _total = await list_audit_logs(
        session, tenant_id=principal.tenant_id, limit=limit, offset=offset, action=action
    )
    return [
        AuditLogOut(
            id=r.id, tenant_id=r.tenant_id, actor=r.actor, action=r.action,
            target=r.target, request_id=r.request_id, result=r.result,
            details=r.details or {}, at=r.at,
        )
        for r in rows
    ]

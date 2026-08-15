"""Role-based access control.

Roles form a strict hierarchy. Each role inherits the permissions of the roles
below it. Scopes are the atomic permissions checked by the API key layer.
"""
from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    owner = "owner"
    admin = "admin"
    developer = "developer"
    analyst = "analyst"
    viewer = "viewer"


# Higher number = more privilege. require_role compares against this.
ROLE_RANK = {
    Role.viewer: 0,
    Role.analyst: 1,
    Role.developer: 2,
    Role.admin: 3,
    Role.owner: 4,
}


def role_satisfies(actual: str, required: Role) -> bool:
    try:
        return ROLE_RANK[Role(actual)] >= ROLE_RANK[required]
    except (KeyError, ValueError):
        return False


ALL_SCOPES = {
    "memory:read",
    "memory:write",
    "graph:read",
    "sessions:read",
    "analytics:read",
    "admin",
}

# Default scopes granted to an API key created by a given role.
DEFAULT_SCOPES_FOR_ROLE = {
    Role.owner: ALL_SCOPES,
    Role.admin: ALL_SCOPES,
    Role.developer: {"memory:read", "memory:write", "graph:read", "sessions:read"},
    Role.analyst: {"memory:read", "graph:read", "sessions:read", "analytics:read"},
    Role.viewer: {"memory:read"},
}


def scope_satisfies(granted: list[str], required: str) -> bool:
    return "admin" in granted or required in granted


def effective_role(principal_role: str, *, kind: str, scopes: list[str]) -> str:
    """Role used for require_role checks. API keys with admin scope act as admin."""
    if kind == "api_key" and "admin" in scopes:
        return Role.admin.value
    return principal_role

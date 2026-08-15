#!/usr/bin/env python3
"""MEMORY OS MCP stdio entrypoint.

Run from repo root:
  pip install -r mcp/requirements.txt
  python scripts/mcp_stdio_server.py

Uses the installed `mcp` PyPI package for protocol handling and loads tool
functions from mcp/server.py without package-name collision.
"""
from __future__ import annotations

import os
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if not os.environ.get("MEMORY_OS_API_KEY"):
    raise SystemExit("MEMORY_OS_API_KEY is required for the MCP server.")

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:
    raise SystemExit("Install MCP deps: pip install -r mcp/requirements.txt") from exc

_spec = importlib.util.spec_from_file_location("memoryos_mcp_tools", ROOT / "mcp" / "server.py")
_api = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_api)

mcp = FastMCP("memory-os")


@mcp.tool()
def memory_create(
    content: str,
    memory_type: str = "observation",
    subject: str | None = None,
    predicate: str | None = None,
    object_value: str | None = None,
) -> dict:
    """Create a memory record."""
    return _api.memory_create(
        content, memory_type=memory_type,
        subject=subject, predicate=predicate, object_value=object_value,
    )


@mcp.tool()
def memory_search(query: str, mode: str = "hybrid", top_k: int = 8, session_id: str | None = None) -> dict:
    """Hybrid memory search."""
    return _api.memory_search(query, mode=mode, top_k=top_k, session_id=session_id)


@mcp.tool()
def memory_get(memory_id: str) -> dict:
    """Get memory by ID."""
    return _api.memory_get(memory_id)


@mcp.tool()
def memory_update(memory_id: str, content: str | None = None, confidence: float | None = None) -> dict:
    """Update memory fields."""
    fields = {k: v for k, v in {"content": content, "confidence": confidence}.items() if v is not None}
    return _api.memory_update(memory_id, **fields)


@mcp.tool()
def memory_delete(memory_id: str) -> str:
    """Delete a memory."""
    _api.memory_delete(memory_id)
    return "deleted"


@mcp.tool()
def memory_extract(content: str, store: bool = False) -> dict:
    """Deterministic extraction (no LLM)."""
    return _api.memory_extract(content, store=store)


@mcp.tool()
def memory_context(query: str) -> dict:
    """Build agent context bundle."""
    return _api.memory_context(query)


@mcp.tool()
def memory_timeline(memory_id: str) -> dict:
    """Temporal timeline for a memory."""
    return _api.memory_timeline(memory_id)


@mcp.tool()
def memory_provenance(memory_id: str) -> dict:
    """Provenance chain."""
    return _api.memory_provenance(memory_id)


@mcp.tool()
def memory_graph(depth: int = 2, limit: int = 50) -> dict:
    """Knowledge graph snapshot."""
    return _api.memory_graph(depth=depth, limit=limit)


@mcp.tool()
def session_create(agent_id: str | None = None) -> dict:
    """Create agent session."""
    return _api.session_create(agent_id)


@mcp.tool()
def session_events(session_id: str) -> dict:
    """Session replay events."""
    return _api.session_events(session_id)


if __name__ == "__main__":
    mcp.run()

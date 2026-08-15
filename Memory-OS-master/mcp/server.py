"""MEMORY OS MCP server (v0.3).

Exposes MEMORY OS as MCP tools. Contains NO LLM. Each tool proxies the REST API.
"""
from __future__ import annotations

import os
import time
from typing import Any

import httpx

API_URL = os.environ.get("MEMORY_OS_API_URL", "http://localhost:8000")
API_KEY = os.environ.get("MEMORY_OS_API_KEY", "")
TIMEOUT = float(os.environ.get("MEMORY_OS_TIMEOUT", "15"))


class McpApiError(Exception):
    def __init__(self, code: str, message: str, status: int = 502):
        self.code = code
        self.status = status
        super().__init__(message)


def _require_api_key() -> None:
    if not API_KEY:
        raise RuntimeError(
            "MEMORY_OS_API_KEY is required. Set it before starting the MCP server."
        )


def _client() -> httpx.Client:
    _require_api_key()
    return httpx.Client(
        base_url=API_URL,
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=TIMEOUT,
    )


def _request(method: str, path: str, *, json: dict | None = None, params: dict | None = None) -> Any:
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            with _client() as c:
                r = c.request(method, path, json=json, params=params)
            if r.status_code >= 400:
                try:
                    err = r.json().get("error", {})
                except Exception:
                    err = {}
                raise McpApiError(
                    err.get("code", "API_ERROR"),
                    err.get("message", r.text or f"HTTP {r.status_code}"),
                    r.status_code,
                )
            return r.json() if r.content else None
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            last_err = exc
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    raise McpApiError("CONNECTION_ERROR", str(last_err or "Unable to reach MEMORY OS API"))


def memory_create(content: str, memory_type: str = "observation",
                  embedding: list[float] | None = None, metadata: dict | None = None,
                  subject: str | None = None, predicate: str | None = None,
                  object_value: str | None = None) -> dict:
    body = {"content": content, "memory_type": memory_type,
            "embedding": embedding, "metadata": metadata or {}}
    if subject:
        body["subject"] = subject
    if predicate:
        body["predicate"] = predicate
    if object_value:
        body["object_value"] = object_value
    return _request("POST", "/v1/memory", json=body)


def memory_search(query: str, mode: str = "hybrid", embedding: list[float] | None = None,
                  top_k: int = 8, session_id: str | None = None) -> dict:
    body = {"query": query, "mode": mode, "embedding": embedding, "top_k": top_k}
    if session_id:
        body["session_id"] = session_id
    return _request("POST", "/v1/memory/search", json=body)


def memory_get(memory_id: str) -> dict:
    return _request("GET", f"/v1/memory/{memory_id}")


def memory_update(memory_id: str, **fields) -> dict:
    return _request("PATCH", f"/v1/memory/{memory_id}", json=fields)


def memory_delete(memory_id: str) -> None:
    _request("DELETE", f"/v1/memory/{memory_id}")


def memory_extract(content: str, store: bool = False) -> dict:
    return _request("POST", "/v1/memory/extract", json={"content": content, "store": store})


def memory_context(query: str, embedding: list[float] | None = None) -> dict:
    return _request("POST", "/v1/context", json={"query": query, "embedding": embedding})


def memory_timeline(memory_id: str) -> dict:
    return _request("GET", f"/v1/memory/{memory_id}/timeline")


def memory_provenance(memory_id: str) -> dict:
    return _request("GET", f"/v1/memory/{memory_id}/provenance")


def memory_graph(depth: int = 2, limit: int = 50) -> dict:
    return _request("GET", "/v1/graph", params={"depth": depth, "limit": limit})


def session_create(agent_id: str | None = None) -> dict:
    body = {"agent_id": agent_id} if agent_id else {}
    return _request("POST", "/v1/sessions", json=body)


def session_events(session_id: str) -> dict:
    return _request("GET", f"/v1/sessions/{session_id}/events")


TOOLS = {
    "memory_create": memory_create,
    "memory_search": memory_search,
    "memory_get": memory_get,
    "memory_update": memory_update,
    "memory_delete": memory_delete,
    "memory_extract": memory_extract,
    "memory_context": memory_context,
    "memory_timeline": memory_timeline,
    "memory_provenance": memory_provenance,
    "memory_graph": memory_graph,
    "session_create": session_create,
    "session_events": session_events,
}

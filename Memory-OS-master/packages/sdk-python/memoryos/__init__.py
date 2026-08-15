"""Official MEMORY OS Python SDK (v0.3).

MEMORY OS is model-independent — you supply embeddings; the SDK never generates
them. Handles auth, request IDs, and typed errors.
"""
from __future__ import annotations

import os
import uuid
import httpx


class MemoryOSError(Exception):
    def __init__(self, code: str, message: str, request_id: str | None):
        self.code, self.request_id = code, request_id
        super().__init__(f"[{code}] {message} (request_id={request_id})")


class _BaseApi:
    def __init__(self, http: httpx.Client):
        self._http = http

    def _req(
        self,
        method: str,
        path: str,
        body: dict | None,
        *,
        params: dict | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        headers = {"X-Request-ID": f"req_{uuid.uuid4().hex[:16]}"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        r = self._http.request(method, path, json=body, params=params, headers=headers)
        if r.status_code >= 400:
            err = r.json().get("error", {})
            raise MemoryOSError(
                err.get("code", "UNKNOWN"),
                err.get("message", "error"),
                err.get("request_id"),
            )
        return r.json() if r.content else {}


class _Memories(_BaseApi):
    def create(
        self,
        content: str,
        *,
        memory_type: str = "observation",
        embedding: list[float] | None = None,
        metadata: dict | None = None,
        confidence: float = 0.5,
        subject: str | None = None,
        predicate: str | None = None,
        object_value: str | None = None,
        supersedes: list[str] | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        body: dict = {
            "content": content,
            "memory_type": memory_type,
            "embedding": embedding,
            "metadata": metadata or {},
            "confidence": confidence,
        }
        if subject:
            body["subject"] = subject
        if predicate:
            body["predicate"] = predicate
        if object_value:
            body["object_value"] = object_value
        if supersedes:
            body["supersedes"] = supersedes
        return self._req("POST", "/v1/memory", body, idempotency_key=idempotency_key)

    def update(self, memory_id: str, **fields) -> dict:
        return self._req("PATCH", f"/v1/memory/{memory_id}", fields)

    def delete(self, memory_id: str) -> dict:
        return self._req("DELETE", f"/v1/memory/{memory_id}", None)

    def search(
        self,
        query: str,
        *,
        mode: str = "hybrid",
        embedding: list[float] | None = None,
        top_k: int = 8,
        **kwargs,
    ) -> dict:
        body = {"query": query, "mode": mode, "embedding": embedding, "top_k": top_k, **kwargs}
        return self._req("POST", "/v1/memory/search", body)

    def extract(
        self,
        content: str,
        *,
        source: dict | None = None,
        store: bool = False,
        structured_facts: list | None = None,
    ) -> dict:
        return self._req(
            "POST",
            "/v1/memory/extract",
            {
                "content": content,
                "source": source or {"type": "api"},
                "store": store,
                "structured_facts": structured_facts,
            },
        )

    def as_of(self, as_of: str, *, subject: str | None = None, predicate: str | None = None) -> dict:
        return self._req(
            "POST",
            "/v1/memory/as-of",
            {"as_of": as_of, "subject": subject, "predicate": predicate},
        )

    def timeline(self, memory_id: str) -> dict:
        return self._req("GET", f"/v1/memory/{memory_id}/timeline", None)

    def provenance(self, memory_id: str) -> dict:
        return self._req("GET", f"/v1/memory/{memory_id}/provenance", None)

    def get(self, memory_id: str) -> dict:
        return self._req("GET", f"/v1/memory/{memory_id}", None)

    def export(self, *, user_id: str | None = None) -> dict:
        return self._req("POST", "/v1/memory/export", {"user_id": user_id})


class _Context(_BaseApi):
    def build(self, query: str, *, embedding: list[float] | None = None, **kwargs) -> dict:
        return self._req("POST", "/v1/context", {"query": query, "embedding": embedding, **kwargs})


class _Benchmarks(_BaseApi):
    def run(
        self,
        *,
        name: str = "memorybench",
        scale: int = 1000,
        categories: list | None = None,
    ) -> dict:
        return self._req(
            "POST",
            "/v1/benchmarks/run",
            {"name": name, "scale": scale, "categories": categories},
        )

    def get(self, run_id: str) -> dict:
        return self._req("GET", f"/v1/benchmarks/{run_id}", None)

    def list(self) -> list:
        return self._req("GET", "/v1/benchmarks", None)


class _Sessions(_BaseApi):
    def create(self, *, agent_id: str | None = None) -> dict:
        body = {"agent_id": agent_id} if agent_id else {}
        return self._req("POST", "/v1/sessions", body)

    def list(self, *, limit: int = 25, offset: int = 0, status: str | None = None) -> dict:
        params: dict = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        return self._req("GET", "/v1/sessions", None, params=params)

    def get(self, session_id: str) -> dict:
        return self._req("GET", f"/v1/sessions/{session_id}", None)

    def events(self, session_id: str) -> dict:
        return self._req("GET", f"/v1/sessions/{session_id}/events", None)

    def append_event(
        self,
        session_id: str,
        *,
        event_type: str,
        detail: str,
        latency_ms: int | None = None,
        payload: dict | None = None,
    ) -> dict:
        body = {"event_type": event_type, "detail": detail}
        if latency_ms is not None:
            body["latency_ms"] = latency_ms
        if payload:
            body["payload"] = payload
        return self._req("POST", f"/v1/sessions/{session_id}/events", body)


class _Operations(_BaseApi):
    def reflection(self, *, stale_days: int = 90) -> dict:
        return self._req("POST", f"/v1/operations/reflection?stale_days={stale_days}", None)

    def reflection_execute(
        self,
        *,
        stale_days: int = 90,
        dry_run: bool = True,
        max_actions: int = 100,
        action_types: list[str] | None = None,
    ) -> dict:
        body: dict = {"stale_days": stale_days, "dry_run": dry_run, "max_actions": max_actions}
        if action_types:
            body["action_types"] = action_types
        return self._req("POST", "/v1/operations/reflection/execute", body)


class MemoryOS:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        api_key = api_key or os.environ.get("MEMORY_OS_API_KEY", "")
        base_url = base_url or os.environ.get("MEMORY_OS_API_URL", "http://localhost:8000")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.Client(base_url=base_url, headers=headers, timeout=15.0)
        self.memory = _Memories(self._http)
        self.context = _Context(self._http)
        self.benchmarks = _Benchmarks(self._http)
        self.sessions = _Sessions(self._http)
        self.operations = _Operations(self._http)

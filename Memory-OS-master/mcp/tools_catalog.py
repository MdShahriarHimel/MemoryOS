"""Tool metadata for MCP docs and dashboard (keep in sync with TOOLS in server.py)."""

TOOL_CATALOG = [
    {"name": "memory_create", "category": "memory", "summary": "Create a memory record"},
    {"name": "memory_search", "category": "memory", "summary": "Hybrid memory search"},
    {"name": "memory_get", "category": "memory", "summary": "Fetch a memory by ID"},
    {"name": "memory_update", "category": "memory", "summary": "Patch memory fields"},
    {"name": "memory_delete", "category": "memory", "summary": "Delete a memory"},
    {"name": "memory_extract", "category": "memory", "summary": "Deterministic fact extraction"},
    {"name": "memory_context", "category": "context", "summary": "Build agent-ready context bundle"},
    {"name": "memory_timeline", "category": "temporal", "summary": "Supersession / validity timeline"},
    {"name": "memory_provenance", "category": "temporal", "summary": "Provenance chain for a memory"},
    {"name": "memory_graph", "category": "graph", "summary": "Knowledge graph snapshot"},
    {"name": "session_create", "category": "sessions", "summary": "Start an agent session"},
    {"name": "session_events", "category": "sessions", "summary": "Replay events for a session"},
]

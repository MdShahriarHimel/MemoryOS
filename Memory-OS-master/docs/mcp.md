# MEMORY OS MCP Server

The MCP server exposes MEMORY OS as [Model Context Protocol](https://modelcontextprotocol.io) tools for Cursor, Claude Desktop, VS Code, and other MCP clients. Each tool is a thin, typed proxy to the REST API — **no LLM and no embedding generation** inside MEMORY OS.

## Tools (v0.3)

| Tool | Description |
|------|-------------|
| `memory_create` | Create a memory |
| `memory_search` | Hybrid retrieval (optional `session_id` for replay) |
| `memory_get` | Fetch memory by ID |
| `memory_update` | Patch memory fields |
| `memory_delete` | Delete a memory |
| `memory_extract` | Deterministic fact extraction |
| `memory_context` | Build agent-ready context |
| `memory_timeline` | Supersession / validity chain |
| `memory_provenance` | Provenance metadata |
| `memory_graph` | Knowledge graph snapshot |
| `session_create` | Start agent session |
| `session_events` | Session replay events |

Implementation: `mcp/server.py` (REST proxies) + `scripts/mcp_stdio_server.py` (MCP protocol).

## Prerequisites

1. MEMORY OS API running (default `http://localhost:8000`)
2. API key with appropriate scopes (create at `/api-keys` in the dashboard)
3. Python 3.11+

```bash
pip install -r mcp/requirements.txt
```

## Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `MEMORY_OS_API_URL` | No | API base URL (default `http://localhost:8000`) |
| `MEMORY_OS_API_KEY` | Recommended | `mos_…` bearer token |

## Cursor configuration

Add to `.cursor/mcp.json` (project) or Cursor Settings → MCP:

```json
{
  "mcpServers": {
    "memory-os": {
      "command": "python",
      "args": ["scripts/mcp_stdio_server.py"],
      "cwd": "/absolute/path/to/memory-os",
      "env": {
        "MEMORY_OS_API_URL": "http://localhost:8000",
        "MEMORY_OS_API_KEY": "mos_your_key_here"
      }
    }
  }
}
```

On Windows, use forward slashes or escaped backslashes in `cwd`.

## Claude Desktop

`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "memory-os": {
      "command": "python",
      "args": ["-m", "mcp.stdio_server"],
      "cwd": "C:/path/to/memory-os",
      "env": {
        "MEMORY_OS_API_URL": "http://localhost:8000",
        "MEMORY_OS_API_KEY": "mos_your_key_here"
      }
    }
  }
}
```

## Manual smoke test

```bash
cd memory-os
export MEMORY_OS_API_URL=http://localhost:8000
export MEMORY_OS_API_KEY=mos_...
python -c "from mcp.server import memory_search; print(memory_search('test'))"
```

## Design principles

- **Model-independent** — agents bring their own LLM; MEMORY OS stores and retrieves memory only.
- **Honest errors** — API error envelopes propagate; no silent fallbacks.
- **Session replay** — pass `session_id` on `memory_search` / memory writes to record events for `/replay`.

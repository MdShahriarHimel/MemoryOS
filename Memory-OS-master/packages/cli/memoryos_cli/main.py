"""MEMORY OS production CLI."""
from __future__ import annotations

import json
import os
import sys

import httpx
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="memoryos", help="MEMORY OS command-line interface")
console = Console()

DEFAULT_BASE = os.environ.get("MEMORY_OS_API_URL", "http://localhost:8000")


def _client(base: str, token: str | None) -> httpx.Client:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(base_url=base.rstrip("/"), headers=headers, timeout=30.0)


def _print_json(data: object) -> None:
    console.print_json(json.dumps(data, default=str))


@app.command("health")
def health(
    base_url: str = typer.Option(DEFAULT_BASE, envvar="MEMORY_OS_API_URL"),
) -> None:
    """Check API health."""
    with _client(base_url, None) as c:
        r = c.get("/v1/health")
        r.raise_for_status()
        _print_json(r.json())


@app.command("memory-create")
def memory_create(
    content: str = typer.Argument(...),
    memory_type: str = typer.Option("observation", "--type"),
    base_url: str = typer.Option(DEFAULT_BASE, envvar="MEMORY_OS_API_URL"),
    token: str | None = typer.Option(None, envvar="MEMORY_OS_TOKEN"),
) -> None:
    """Create a memory."""
    with _client(base_url, token) as c:
        r = c.post("/v1/memory", json={"content": content, "memory_type": memory_type})
        r.raise_for_status()
        _print_json(r.json())


@app.command("memory-search")
def memory_search(
    query: str = typer.Argument(...),
    mode: str = typer.Option("hybrid", "--mode"),
    top_k: int = typer.Option(8, "--top-k"),
    rerank: bool = typer.Option(True, "--rerank/--no-rerank"),
    base_url: str = typer.Option(DEFAULT_BASE, envvar="MEMORY_OS_API_URL"),
    token: str | None = typer.Option(None, envvar="MEMORY_OS_TOKEN"),
) -> None:
    """Search memories."""
    with _client(base_url, token) as c:
        r = c.post(
            "/v1/memory/search",
            json={"query": query, "mode": mode, "top_k": top_k, "rerank": rerank},
        )
        r.raise_for_status()
        data = r.json()
        table = Table(title=f"Search: {query}")
        table.add_column("ID", style="cyan")
        table.add_column("Score")
        table.add_column("Content")
        for item in data.get("results", []):
            m = item["memory"]
            table.add_row(m["id"][:8], f"{item['score']:.4f}", m["content"][:80])
        console.print(table)


@app.command("usage")
def usage(
    base_url: str = typer.Option(DEFAULT_BASE, envvar="MEMORY_OS_API_URL"),
    token: str | None = typer.Option(None, envvar="MEMORY_OS_TOKEN"),
) -> None:
    """Show usage metering summary."""
    with _client(base_url, token) as c:
        r = c.get("/v1/metering/usage")
        r.raise_for_status()
        _print_json(r.json())


@app.command("reflect")
def reflect(
    base_url: str = typer.Option(DEFAULT_BASE, envvar="MEMORY_OS_API_URL"),
    token: str | None = typer.Option(None, envvar="MEMORY_OS_TOKEN"),
) -> None:
    """Run consolidation/reflection scan."""
    with _client(base_url, token) as c:
        r = c.post("/v1/operations/reflection")
        r.raise_for_status()
        _print_json(r.json())


@app.command("developer")
def developer_info(
    base_url: str = typer.Option(DEFAULT_BASE, envvar="MEMORY_OS_API_URL"),
) -> None:
    """Show developer portal index from the API."""
    with _client(base_url, None) as c:
        r = c.get("/developer")
        r.raise_for_status()
        _print_json(r.json())


def main() -> None:
    app()


if __name__ == "__main__":
    main()

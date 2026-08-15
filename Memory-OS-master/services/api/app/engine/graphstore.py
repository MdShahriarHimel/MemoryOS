"""Knowledge-graph store abstraction.

Neo4j is the traversal engine in production. A relational fallback (backed by the
graph_nodes / graph_edges tables) keeps the graph queryable in dev and test when
Neo4j is not configured. Both enforce tenant isolation.

MEMORY OS does not infer entities with an LLM. Entities/relationships are either
supplied by the client in memory metadata or created explicitly via the graph API.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import GraphEdge, GraphNode


@dataclass
class GraphNodeDTO:
    id: str
    key: str
    entity_type: str
    label: str


@dataclass
class GraphEdgeDTO:
    source_id: str
    target_id: str
    rel_type: str
    confidence: float


@dataclass
class GraphView:
    nodes: list[GraphNodeDTO]
    edges: list[GraphEdgeDTO]


class GraphStore(ABC):
    @abstractmethod
    async def upsert_node(self, tenant_id: str, key: str, entity_type: str, label: str) -> str: ...

    @abstractmethod
    async def upsert_edge(
        self, tenant_id: str, source_key: str, target_key: str, rel_type: str,
        *, confidence: float, source_memory_id: str | None,
    ) -> None: ...

    @abstractmethod
    async def neighborhood(self, tenant_id: str, *, depth: int, limit: int) -> GraphView: ...


class RelationalGraphStore(GraphStore):
    """Fallback graph store using Postgres/SQLite tables. Correct, tenant-scoped,
    good for moderate graphs. Neo4j takes over for deep traversal at scale."""

    def __init__(self, session_factory):
        self._sf = session_factory

    async def upsert_node(self, tenant_id: str, key: str, entity_type: str, label: str) -> str:
        async with self._sf() as s:
            existing = (
                await s.execute(
                    select(GraphNode).where(GraphNode.tenant_id == tenant_id, GraphNode.key == key)
                )
            ).scalar_one_or_none()
            if existing:
                existing.label = label
                existing.entity_type = entity_type
                await s.commit()
                return existing.id
            node = GraphNode(tenant_id=tenant_id, key=key, entity_type=entity_type, label=label)
            s.add(node)
            await s.commit()
            await s.refresh(node)
            return node.id

    async def upsert_edge(self, tenant_id, source_key, target_key, rel_type, *, confidence, source_memory_id):
        src = await self.upsert_node(tenant_id, source_key, "Concept", source_key)
        tgt = await self.upsert_node(tenant_id, target_key, "Concept", target_key)
        async with self._sf() as s:
            exists = (
                await s.execute(
                    select(GraphEdge).where(
                        GraphEdge.tenant_id == tenant_id,
                        GraphEdge.source_id == src,
                        GraphEdge.target_id == tgt,
                        GraphEdge.rel_type == rel_type,
                    )
                )
            ).scalar_one_or_none()
            if exists:
                exists.confidence = confidence
            else:
                s.add(GraphEdge(
                    tenant_id=tenant_id, source_id=src, target_id=tgt, rel_type=rel_type,
                    confidence=confidence, source_memory_id=source_memory_id,
                ))
            await s.commit()

    async def neighborhood(self, tenant_id: str, *, depth: int, limit: int) -> GraphView:
        async with self._sf() as s:
            nodes = (
                await s.execute(
                    select(GraphNode).where(GraphNode.tenant_id == tenant_id).limit(limit)
                )
            ).scalars().all()
            edges = (
                await s.execute(
                    select(GraphEdge).where(GraphEdge.tenant_id == tenant_id).limit(limit * 3)
                )
            ).scalars().all()
        return GraphView(
            nodes=[GraphNodeDTO(n.id, n.key, n.entity_type, n.label) for n in nodes],
            edges=[GraphEdgeDTO(e.source_id, e.target_id, e.rel_type, e.confidence) for e in edges],
        )


class Neo4jGraphStore(GraphStore):
    """Neo4j-backed store. Requires the `neo4j` driver and NEO4J_URI configured.
    Cypher enforces tenant isolation via a `tenant` property on every node/edge."""

    def __init__(self, uri: str, user: str, password: str):
        from neo4j import AsyncGraphDatabase  # imported lazily

        self._driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def upsert_node(self, tenant_id, key, entity_type, label) -> str:
        async with self._driver.session() as s:
            rec = await s.run(
                "MERGE (n:Entity {tenant:$t, key:$k}) "
                "SET n.type=$type, n.label=$label RETURN elementId(n) AS id",
                t=tenant_id, k=key, type=entity_type, label=label,
            )
            row = await rec.single()
            return row["id"]

    async def upsert_edge(self, tenant_id, source_key, target_key, rel_type, *, confidence, source_memory_id):
        async with self._driver.session() as s:
            await s.run(
                "MERGE (a:Entity {tenant:$t, key:$sk}) "
                "MERGE (b:Entity {tenant:$t, key:$tk}) "
                "MERGE (a)-[r:REL {type:$rt}]->(b) "
                "SET r.confidence=$c, r.source_memory=$sm",
                t=tenant_id, sk=source_key, tk=target_key, rt=rel_type,
                c=confidence, sm=source_memory_id,
            )

    async def neighborhood(self, tenant_id, *, depth, limit) -> GraphView:
        async with self._driver.session() as s:
            rec = await s.run(
                "MATCH (a:Entity {tenant:$t})-[r:REL]->(b:Entity {tenant:$t}) "
                "RETURN a,r,b LIMIT $lim",
                t=tenant_id, lim=limit,
            )
            nodes: dict[str, GraphNodeDTO] = {}
            edges: list[GraphEdgeDTO] = []
            async for row in rec:
                for n in (row["a"], row["b"]):
                    nid = n.element_id
                    nodes[nid] = GraphNodeDTO(nid, n["key"], n.get("type", "Concept"), n.get("label", n["key"]))
                r = row["r"]
                edges.append(GraphEdgeDTO(row["a"].element_id, row["b"].element_id, r["type"], r.get("confidence", 0.5)))
            return GraphView(nodes=list(nodes.values()), edges=edges)


def build_graph_store(session_factory) -> GraphStore:
    s = get_settings()
    if s.neo4j_uri:
        try:
            return Neo4jGraphStore(s.neo4j_uri, s.neo4j_username, s.neo4j_password)
        except Exception:
            pass
    return RelationalGraphStore(session_factory)


async def delete_neo4j_memory_refs(tenant_id: str, memory_id: str) -> bool:
    """Remove graph edges in Neo4j that reference a deleted memory."""
    s = get_settings()
    if not s.neo4j_uri:
        return False
    try:
        from neo4j import AsyncGraphDatabase

        driver = AsyncGraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_username, s.neo4j_password))
        async with driver.session() as session:
            await session.run(
                "MATCH (a:Entity {tenant:$t})-[r:REL]->() "
                "WHERE r.source_memory = $mid DELETE r",
                t=tenant_id,
                mid=memory_id,
            )
        await driver.close()
        return True
    except Exception:
        return False

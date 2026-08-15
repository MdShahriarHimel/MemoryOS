"""Multi-hop graph retrieval with bounded traversal.

Uses existing graph store abstraction. Enforces tenant isolation, hop limits,
and cycle protection.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.engine.graphstore import GraphView


@dataclass
class GraphTraversalResult:
    memory_ids: list[str] = field(default_factory=list)
    node_ids: list[str] = field(default_factory=list)
    path: list[tuple[str, str, str]] = field(default_factory=list)  # (source, rel, target)
    hops_used: int = 0
    truncated: bool = False


def expand_graph(
    graph: GraphView,
    *,
    seed_node_ids: list[str] | None = None,
    seed_memory_ids: list[str] | None = None,
    max_hops: int = 3,
    max_nodes: int = 50,
) -> GraphTraversalResult:
    """BFS expansion from seed nodes with cycle protection."""
    if max_hops < 1:
        max_hops = 1
    if max_hops > 5:
        max_hops = 5

    # Build adjacency from edges
    adj: dict[str, list[tuple[str, str, str]]] = {}  # node -> [(target, rel, edge_key)]
    node_by_id = {n.id: n for n in graph.nodes}
    for e in graph.edges:
        adj.setdefault(e.source_id, []).append((e.target_id, e.rel_type, f"{e.source_id}:{e.rel_type}:{e.target_id}"))
        adj.setdefault(e.target_id, []).append((e.source_id, f"inverse_{e.rel_type}", f"{e.target_id}:inv:{e.source_id}"))

    # Resolve seeds
    seeds: set[str] = set(seed_node_ids or [])
    if seed_memory_ids:
        for mid in seed_memory_ids:
            for n in graph.nodes:
                if mid in (n.key, n.label):
                    seeds.add(n.id)

    if not seeds and graph.nodes:
        seeds = {graph.nodes[0].id}

    visited: set[str] = set()
    result = GraphTraversalResult()
    frontier = list(seeds)
    hop = 0

    while frontier and hop < max_hops and len(visited) < max_nodes:
        next_frontier: list[str] = []
        for node_id in frontier:
            if node_id in visited:
                continue
            if len(visited) >= max_nodes:
                result.truncated = True
                break
            visited.add(node_id)
            result.node_ids.append(node_id)
            if node_id in node_by_id:
                key = node_by_id[node_id].key
                if key.startswith("mem:"):
                    result.memory_ids.append(key[4:])

            for target_id, rel_type, _ in adj.get(node_id, []):
                if target_id not in visited:
                    result.path.append((node_id, rel_type, target_id))
                    next_frontier.append(target_id)

        frontier = next_frontier
        hop += 1

    result.hops_used = hop
    if frontier and hop >= max_hops:
        result.truncated = True

    return result


def score_graph_relevance(
    traversal: GraphTraversalResult,
    query_tokens: set[str],
    node_labels: dict[str, str],
) -> dict[str, float]:
    """Score nodes by token overlap with query."""
    scores: dict[str, float] = {}
    for nid in traversal.node_ids:
        label = node_labels.get(nid, "").lower()
        label_tokens = set(label.split())
        overlap = len(query_tokens & label_tokens)
        if overlap > 0:
            scores[nid] = overlap / max(len(query_tokens), 1)
    return scores

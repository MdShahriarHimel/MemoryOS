"""Tests for production-grade engines."""
from datetime import datetime, timedelta, timezone

from app.engine.conflicts import MemoryConflictInput, analyze_conflicts
from app.engine.deduplication import MemoryRecord, find_duplicates
from app.engine.reranker import RerankInput, rerank
from app.engine.ranking import Candidate, RankedResult, fuse_and_rank
from app.engine.temporal import TemporalMemory, is_valid_at, query_as_of


def test_deduplication_exact_match():
    mems = [
        MemoryRecord("a", "User prefers dark mode"),
        MemoryRecord("b", "user prefers dark mode"),
    ]
    clusters = find_duplicates(mems)
    assert len(clusters) >= 1
    assert clusters[0].canonical_id in ("a", "b")


def test_advanced_conflict_negation():
    reports = analyze_conflicts([
        MemoryConflictInput("a", "Alice likes coffee"),
        MemoryConflictInput("b", "Alice does not like coffee"),
    ])
    assert any("negation_flip" in r.signals for r in reports)


def test_reranker_boosts_overlap():
    base = fuse_and_rank(
        [Candidate("m1", channels={"keyword": 0}, quality=0.5, importance=0.5)],
        top_k=1,
    )[0]
    now = datetime.now(timezone.utc)
    results = rerank(
        "dark mode",
        [
            RerankInput("m1", "User prefers dark mode", base, now, now, 0.5, 0.5),
        ],
        top_k=1,
        now=now,
    )
    assert results[0].score >= base.score


def test_temporal_as_of_supersedes():
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    t1 = datetime(2024, 6, 1, tzinfo=timezone.utc)
    memories = [
        TemporalMemory("v1", "old fact", 1, t0, t1, t0, t1, None, t0),
        TemporalMemory("v2", "new fact", 2, t1, None, t1, None, "v1", t1),
    ]
    assert not is_valid_at(memories[0], datetime(2024, 7, 1, tzinfo=timezone.utc))
    results = query_as_of(memories, datetime(2024, 7, 1, tzinfo=timezone.utc))
    assert any(r.memory_id == "v2" for r in results)

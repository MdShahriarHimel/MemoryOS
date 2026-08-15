"""Deterministic engine + tenant isolation tests.

These run with no external services (SQLite + in-memory vector store).
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.engine.quality import QualitySignals, compute_quality, freshness_score
from app.engine.ranking import Candidate, fuse_and_rank
from app.engine.retrieval import BM25Lite, KeywordDoc, detect_conflicts
from app.engine.vectorstore import InMemoryVectorStore


def test_quality_is_deterministic():
    sig = QualitySignals(0.8, 0.7, datetime.now(timezone.utc), 5, True, 0)
    a = compute_quality(sig)
    b = compute_quality(sig)
    assert a.score == b.score
    assert 0 <= a.score <= 1


def test_freshness_decays_with_age():
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=60)
    assert freshness_score(now) > freshness_score(old)


def test_ranking_is_stable_and_ordered():
    cands = [
        Candidate("m2", channels={"vector": 1, "keyword": 3}, quality=0.5, importance=0.2),
        Candidate("m1", channels={"vector": 0}, quality=0.9, importance=0.8),
        Candidate("m3", channels={"keyword": 0}, quality=0.4, importance=0.1),
    ]
    r1 = fuse_and_rank(cands, top_k=3)
    r2 = fuse_and_rank(list(reversed(cands)), top_k=3)
    assert [x.memory_id for x in r1] == [x.memory_id for x in r2]  # deterministic
    assert r1[0].score >= r1[1].score >= r1[2].score


def test_bm25_finds_relevant_doc():
    docs = [
        KeywordDoc("a", ["user", "prefers", "dark", "mode"]),
        KeywordDoc("b", ["weather", "is", "sunny", "today"]),
    ]
    hits = BM25Lite(docs).search("dark mode preference", limit=5)
    assert hits[0][0] == "a"


def test_conflict_detection_flags_candidates():
    mems = [
        ("a", "Alice lives in Dhaka"),
        ("b", "Alice lives in Sylhet"),
    ]
    signals = detect_conflicts("alice", mems)
    assert any({s.memory_a, s.memory_b} == {"a", "b"} for s in signals)


@pytest.mark.asyncio
async def test_vector_store_tenant_isolation():
    vs = InMemoryVectorStore()
    await vs.upsert("tenant-a", "m1", [1.0, 0.0, 0.0])
    await vs.upsert("tenant-b", "m2", [1.0, 0.0, 0.0])
    hits_a = await vs.search("tenant-a", [1.0, 0.0, 0.0], limit=10)
    assert [h.memory_id for h in hits_a] == ["m1"]  # never sees tenant-b

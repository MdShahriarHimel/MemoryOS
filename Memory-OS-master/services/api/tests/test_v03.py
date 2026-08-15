"""Tests for MEMORY OS v0.3 — temporal truth, extraction, provenance, context, benchmarks."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.engine.benchmark import run_memorybench
from app.engine.decay import DecayPolicy, DecaySignals, compute_decay_score
from app.engine.evaluation import EvalQuery, evaluate_query, summarize_results
from app.engine.extraction import extract_from_content
from app.engine.truth import (
    CanonicalMemory,
    resolve_current_truth,
    resolve_historical_truth,
)


def _location_chain() -> list[CanonicalMemory]:
    t2024 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    t2025 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    t2026 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        CanonicalMemory(
            "loc_v1", "user", "lives_in", "Sylhet", "User lives in Sylhet",
            1, 0.9, t2024, datetime(2024, 12, 31, tzinfo=timezone.utc),
            t2024, datetime(2025, 1, 1, tzinfo=timezone.utc), None, "loc_v2", t2024,
            status="SUPERSEDED",
        ),
        CanonicalMemory(
            "loc_v2", "user", "lives_in", "Dhaka", "User moved to Dhaka",
            2, 0.92, t2025, datetime(2025, 12, 31, tzinfo=timezone.utc),
            t2025, datetime(2026, 1, 1, tzinfo=timezone.utc), "loc_v1", "loc_v3", t2025,
            status="SUPERSEDED",
        ),
        CanonicalMemory(
            "loc_v3", "user", "lives_in", "Sylhet", "User returned to Sylhet",
            3, 0.94, t2026, None, t2026, None, "loc_v2", None, t2026,
            status="ACTIVE",
        ),
    ]


# ---- Temporal truth -------------------------------------------------------

def test_current_truth_sylhet():
    mems = _location_chain()
    truth = resolve_current_truth(mems, "user", "lives_in")
    assert truth.current_value == "Sylhet"
    assert truth.current_memory_id == "loc_v3"
    assert "loc_v1" in truth.lineage


def test_historical_truth_2025_dhaka():
    mems = _location_chain()
    truth = resolve_historical_truth(
        mems, "user", "lives_in", datetime(2025, 6, 1, tzinfo=timezone.utc)
    )
    assert truth.current_value == "Dhaka"
    assert truth.is_current is False


def test_historical_truth_2024_sylhet():
    mems = _location_chain()
    truth = resolve_historical_truth(
        mems, "user", "lives_in", datetime(2024, 6, 1, tzinfo=timezone.utc)
    )
    assert truth.current_value == "Sylhet"


# ---- Extraction -----------------------------------------------------------

def test_extraction_location():
    result = extract_from_content("I moved from Dhaka back to Sylhet last month.")
    assert len(result.facts) >= 1
    assert result.facts[0].predicate in ("lives_in",)
    assert "Sylhet" in result.facts[0].value


def test_extraction_negation():
    result = extract_from_content("I don't like spicy food anymore")
    assert result.facts[0].polarity == "negative"


def test_extraction_structured():
    result = extract_from_content(
        "some text",
        structured_facts=[{
            "subject": "user", "predicate": "lives_in", "value": "Dhaka", "confidence": 0.95,
        }],
    )
    assert result.method == "hybrid"
    assert result.facts[0].value == "Dhaka"


def test_extraction_no_llm():
    """Verify extraction module has no LLM imports."""
    import app.engine.extraction as mod
    source = open(mod.__file__).read()
    for forbidden in ("openai", "anthropic", "gemini", "ollama", "litellm"):
        assert forbidden not in source.lower()


# ---- Decay ----------------------------------------------------------------

def test_decay_high_importance_slower():
    policy = DecayPolicy()
    high = compute_decay_score(DecaySignals(
        importance=0.9, confidence=0.9, access_count=10,
        memory_type="fact", age_days=30, last_accessed_days=1,
        is_superseded=False, contradiction_status="none",
    ), policy)
    low = compute_decay_score(DecaySignals(
        importance=0.1, confidence=0.3, access_count=0,
        memory_type="event", age_days=30, last_accessed_days=30,
        is_superseded=False, contradiction_status="none",
    ), policy)
    assert high > low


def test_decay_superseded_penalty():
    policy = DecayPolicy()
    active = compute_decay_score(DecaySignals(
        importance=0.5, confidence=0.5, access_count=1,
        memory_type="fact", age_days=60, last_accessed_days=30,
        is_superseded=False, contradiction_status="none",
    ), policy)
    superseded = compute_decay_score(DecaySignals(
        importance=0.5, confidence=0.5, access_count=1,
        memory_type="fact", age_days=60, last_accessed_days=30,
        is_superseded=True, contradiction_status="none",
    ), policy)
    assert active > superseded


# ---- Evaluation -----------------------------------------------------------

def test_eval_recall_at_k():
    eq = EvalQuery("test", ["m1", "m2"], {"m1": 1.0, "m2": 0.8})
    result = evaluate_query(eq, ["m1", "m3", "m2"], latency_ms=5.0)
    assert result.recall_at_k[3] == pytest.approx(1.0)
    assert result.mrr == pytest.approx(1.0)


def test_eval_ndcg():
    eq = EvalQuery("test", ["m1"], {"m1": 1.0})
    result = evaluate_query(eq, ["m1"], latency_ms=1.0)
    assert result.ndcg_at_k[1] == pytest.approx(1.0)


def test_eval_summary():
    results = [
        evaluate_query(EvalQuery("q", ["a"], {"a": 1.0}), ["a"], latency_ms=10.0),
        evaluate_query(EvalQuery("q", ["b"], {"b": 1.0}), ["x", "b"], latency_ms=20.0),
    ]
    summary = summarize_results(results, mode="hybrid")
    assert summary.total_queries == 2
    assert summary.mean_mrr > 0


# ---- MemoryBench ----------------------------------------------------------

def test_memorybench_runs():
    result = run_memorybench(categories=["current_truth_resolution", "fact_retrieval"], scale=1000)
    assert result.total_passed >= 2
    assert result.duration_ms > 0


def test_memorybench_scaffold_categories_real_checks():
    from app.engine.benchmark import run_category_bench

    for cat in ("session_continuity", "long_context_retrieval", "tenant_isolation"):
        r = run_category_bench(cat)
        assert r.failed == 0, f"{cat} should pass with real checks"
        assert r.passed == r.total


def test_memorybench_no_fake_numbers():
    result = run_memorybench(scale=1_000_000)
    assert any("requires external" in n.lower() or "harness" in n.lower() for n in result.notes) or result.scale <= 10000

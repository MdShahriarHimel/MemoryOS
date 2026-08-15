"""Prometheus metrics for MEMORY OS API."""
from __future__ import annotations

try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

    REQUEST_COUNT = Counter(
        "memoryos_http_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
    )
    REQUEST_LATENCY = Histogram(
        "memoryos_http_request_duration_seconds",
        "HTTP request latency",
        ["method", "path"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    )
    MEMORY_WRITES = Counter("memoryos_memory_writes_total", "Memory write operations", ["tenant"])
    MEMORY_SEARCHES = Counter("memoryos_memory_searches_total", "Memory search operations", ["tenant"])
    MEMORY_SUPERSEDED = Counter("memoryos_memory_superseded_total", "Memory supersession events", ["tenant"])
    MEMORY_CONSOLIDATED = Counter("memoryos_memory_consolidated_total", "Memory consolidation events", ["tenant"])
    RETRIEVAL_LATENCY = Histogram(
        "memoryos_retrieval_latency_seconds", "Retrieval latency", ["mode"],
        buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
    )
    RETRIEVAL_CANDIDATES = Histogram(
        "memoryos_retrieval_candidates", "Retrieval candidate counts", ["channel"],
        buckets=(1, 5, 10, 20, 50, 100, 200),
    )
    CONFLICT_DETECTED = Counter("memoryos_conflict_detected_total", "Conflicts detected", ["tenant"])
    CONTEXT_BUILD = Counter("memoryos_context_build_total", "Context build operations", ["tenant"])
    CONTEXT_LATENCY = Histogram(
        "memoryos_context_build_latency_seconds", "Context build latency", [],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
    )
    BENCHMARK_RUN = Counter("memoryos_benchmark_run_total", "Benchmark runs", ["tenant"])
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


def metrics_response():
    if not _AVAILABLE:
        return b"# prometheus_client not installed\n", "text/plain"
    return generate_latest(), CONTENT_TYPE_LATEST

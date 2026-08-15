"""Pydantic v2 request/response schemas."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    episodic = "episodic"
    semantic = "semantic"
    procedural = "procedural"
    preference = "preference"
    fact = "fact"
    decision = "decision"
    goal = "goal"
    task = "task"
    relationship = "relationship"
    observation = "observation"
    event = "event"
    profile = "profile"
    system = "system"
    custom = "custom"


class SearchMode(str, Enum):
    hybrid = "hybrid"
    vector = "vector"
    keyword = "keyword"
    graph = "graph"
    temporal = "temporal"


class MemoryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
    memory_type: MemoryType = MemoryType.observation
    embedding: list[float] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    importance: float = Field(default=0.5, ge=0, le=1)
    confidence: float = Field(default=0.5, ge=0, le=1)
    reliability: float = Field(default=0.5, ge=0, le=1)
    source: str | None = None
    source_id: str | None = None
    user_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    project_id: str | None = None
    observed_at: datetime | None = None
    # Canonical triple (optional)
    subject: str | None = None
    predicate: str | None = None
    object_value: str | None = None
    normalized_content: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    supersedes: list[str] = Field(default_factory=list)
    derived_from: list[str] = Field(default_factory=list)


class MemoryUpdate(BaseModel):
    content: str | None = Field(default=None, max_length=20_000)
    embedding: list[float] | None = None
    metadata: dict[str, Any] | None = None
    importance: float | None = Field(default=None, ge=0, le=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    reliability: float | None = Field(default=None, ge=0, le=1)
    status: str | None = None
    subject: str | None = None
    predicate: str | None = None
    object_value: str | None = None
    # When true and content changes, previous state is preserved as a version.
    preserve_history: bool = True
    supersede: bool = False


class QualityOut(BaseModel):
    score: float
    freshness: float
    usage: float
    provenance: float
    contradiction_penalty: float
    components: dict[str, float]


class MemoryOut(BaseModel):
    id: str
    content: str
    memory_type: str
    importance: float
    confidence: float
    reliability: float
    status: str
    version: int
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    last_accessed_at: datetime | None = None
    quality: QualityOut | None = None
    # v0.3 canonical fields
    subject: str | None = None
    predicate: str | None = None
    object_value: str | None = None
    normalized_content: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    observed_at: datetime | None = None
    superseded_at: datetime | None = None
    supersedes_memory_id: str | None = None
    superseded_by_memory_id: str | None = None
    contradiction_status: str = "none"
    decay_score: float = 1.0
    access_count: int = 0


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    mode: SearchMode = SearchMode.hybrid
    embedding: list[float] | None = None
    top_k: int = Field(default=8, ge=1, le=100)
    memory_type: MemoryType | None = None
    min_confidence: float | None = Field(default=None, ge=0, le=1)
    user_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    rerank: bool = Field(default=True, description="Apply deterministic second-stage reranking")
    max_graph_hops: int = Field(default=2, ge=0, le=5)
    as_of: datetime | None = None
    subject: str | None = None
    predicate: str | None = None


class SearchResultItem(BaseModel):
    memory: MemoryOut
    score: float
    channels: list[str]
    explanation: dict[str, float]
    explanation_summary: str = ""


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    retrieval_trace: dict[str, Any]


class ContextBuildRequest(BaseModel):
    query: str = Field(min_length=1)
    embedding: list[float] | None = None
    user_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    max_tokens: int = Field(default=4000, ge=100, le=32000)


class ContextBuildResponse(BaseModel):
    query: str = ""
    memories: list[MemoryOut]
    current_truths: list[dict[str, Any]] = Field(default_factory=list)
    entities: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    timeline: list[dict[str, Any]]
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    provenance: list[dict[str, Any]]
    retrieval_trace: dict[str, Any]
    max_tokens: int = 4000
    tokens_used: int = 0
    truncated: bool = False
    # MEMORY OS does not produce a final answer.
    note: str = "MEMORY OS constructs context. Your external AI system performs reasoning."


# ---- v0.3 schemas -------------------------------------------------------

class SourceInfo(BaseModel):
    type: str = "api"
    id: str | None = None


class ExtractedFactOut(BaseModel):
    subject: str
    predicate: str
    value: str
    memory_type: str
    confidence: float
    polarity: str = "positive"
    temporal_state: str = "current"
    valid_from: datetime | None = None
    supersedes: list[str] = Field(default_factory=list)
    content: str = ""


class MemoryExtractRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
    source: SourceInfo = Field(default_factory=SourceInfo)
    structured_facts: list[dict[str, Any]] | None = None
    store: bool = Field(default=False, description="If true, persist extracted facts as memories")
    embedding: list[float] | None = None


class MemoryExtractResponse(BaseModel):
    facts: list[ExtractedFactOut]
    method: str
    stored_memory_ids: list[str] = Field(default_factory=list)


class AsOfRequest(BaseModel):
    as_of: datetime
    subject: str | None = None
    predicate: str | None = None
    query: str | None = None


class TruthStateOut(BaseModel):
    subject: str
    predicate: str
    current_value: str | None
    current_memory_id: str | None
    confidence: float
    lineage: list[str] = Field(default_factory=list)
    is_current: bool = True
    as_of: datetime | None = None
    reason: str = ""


class AsOfResponse(BaseModel):
    as_of: datetime
    truths: list[TruthStateOut]
    memories: list[MemoryOut] = Field(default_factory=list)


class TimelineEntry(BaseModel):
    memory_id: str
    content: str
    version: int
    valid_from: datetime | None
    valid_until: datetime | None
    observed_at: datetime | None
    superseded_at: datetime | None
    status: str
    is_current: bool


class TimelineResponse(BaseModel):
    memory_id: str
    chain: list[TimelineEntry]
    current_truth: TruthStateOut | None = None


class ProvenanceOut(BaseModel):
    memory_id: str
    source_type: str | None
    source_id: str | None
    created_by: str | None
    observed_at: datetime | None
    extracted_at: datetime | None
    created_at: datetime | None
    derived_from: list[str] = Field(default_factory=list)
    supersedes: list[str] = Field(default_factory=list)
    evidence: list[Any] = Field(default_factory=list)
    confidence: float | None = None


class BenchmarkRunRequest(BaseModel):
    name: str = "memorybench"
    categories: list[str] | None = None
    scale: int = Field(default=1000, ge=100, le=10_000_000)
    retrieval_modes: list[str] | None = None


class BenchmarkRunOut(BaseModel):
    id: str
    name: str
    status: str
    config: dict[str, Any]
    results: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None = None


class MemoryExportRequest(BaseModel):
    user_id: str | None = None
    format: str = "json"


class MemoryDeleteRequest(BaseModel):
    user_id: str | None = None
    hard_delete: bool = False
    verify: bool = False


class MemoryDeleteResponse(BaseModel):
    deleted_count: int
    verified: bool = False
    stores_cleaned: list[str] = Field(default_factory=list)
    stores_failed: list[dict[str, str]] = Field(default_factory=list)


class Page(BaseModel):
    items: list[MemoryOut]
    total: int
    limit: int
    offset: int


class SessionOut(BaseModel):
    id: str
    tenant_id: str
    agent_id: str | None
    status: str
    started_at: datetime
    ended_at: datetime | None
    event_count: int = 0


class SessionPage(BaseModel):
    items: list[SessionOut]
    total: int
    limit: int
    offset: int


class SessionEventOut(BaseModel):
    seq: int
    t: float
    type: str
    detail: str
    latency_ms: int | None = None


class SessionReplayResponse(BaseModel):
    session_id: str
    started_at: datetime
    events: list[SessionEventOut]


class SessionCreate(BaseModel):
    agent_id: str | None = None


class SessionEventCreate(BaseModel):
    event_type: str = Field(min_length=1, max_length=40)
    detail: str = Field(min_length=1, max_length=2000)
    latency_ms: int | None = Field(default=None, ge=0)
    payload: dict[str, Any] = Field(default_factory=dict)

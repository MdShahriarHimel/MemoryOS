// Shared API types. Mirror the backend Pydantic schemas.

export interface Quality {
  score: number;
  freshness: number;
  usage: number;
  provenance: number;
  contradiction_penalty: number;
  components: Record<string, number>;
}

export interface Memory {
  id: string;
  content: string;
  memory_type: string;
  importance: number;
  confidence: number;
  reliability: number;
  status: string;
  version: number;
  source: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  last_accessed_at: string | null;
  quality?: Quality | null;
  subject?: string | null;
  predicate?: string | null;
  object_value?: string | null;
  decay_score?: number;
  superseded_at?: string | null;
}

export interface ContextBuildResponse {
  query: string;
  memories: Memory[];
  current_truths: Array<Record<string, unknown>>;
  entities: Array<Record<string, unknown>>;
  relationships: Array<Record<string, unknown>>;
  timeline: Array<Record<string, unknown>>;
  conflicts: Array<Record<string, unknown>>;
  provenance: Array<Record<string, unknown>>;
  retrieval_trace: RetrievalTrace;
  note?: string;
}

export interface TimelineEntry {
  memory_id: string;
  content: string;
  version: number;
  valid_from: string | null;
  valid_until: string | null;
  observed_at: string | null;
  superseded_at: string | null;
  status: string;
  is_current: boolean;
}

export interface TimelineResponse {
  memory_id: string;
  chain: TimelineEntry[];
  current_truth: Record<string, unknown> | null;
}

export interface ProvenanceResponse {
  memory_id: string;
  source_type: string | null;
  source_id: string | null;
  derived_from: string[];
  supersedes: string[];
  evidence: unknown[];
  confidence: number | null;
}

export interface RetrievalTrace {
  query: string;
  vector_candidates: number;
  keyword_candidates: number;
  graph_candidates: number;
  merged_candidates: number;
  final_results: number;
  latency_ms: number;
}

export interface SearchResultItem {
  memory: Memory;
  score: number;
  channels: string[];
  explanation: Record<string, number>;
}

export interface SearchResponse {
  results: SearchResultItem[];
  retrieval_trace: RetrievalTrace;
}

export interface AdminStats {
  total_memories: number;
  active_agents: number;
  open_conflicts: number;
  active_sessions: number;
  avg_confidence: number | null;
  retrievals_24h: number | null;
  api_requests_24h: number | null;
}

export interface ReadyState {
  status: "operational" | "degraded" | "unavailable";
  components: Record<string, string>;
}

export interface HealthState {
  status: string;
  time: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface AgentSession {
  id: string;
  tenant_id: string;
  agent_id: string | null;
  status: string;
  started_at: string;
  ended_at: string | null;
  event_count: number;
}

export interface SessionReplayEvent {
  seq: number;
  t: number;
  type: string;
  detail: string;
  latency_ms?: number | null;
}

export interface SessionReplayResponse {
  session_id: string;
  started_at: string;
  events: SessionReplayEvent[];
}

export interface AuditLogEntry {
  id: string;
  tenant_id: string;
  actor: string | null;
  action: string;
  target: string | null;
  request_id: string | null;
  result: string;
  details: Record<string, unknown>;
  at: string;
}

export interface BenchmarkRunOut {
  id: string;
  name: string;
  status: string;
  config: Record<string, unknown>;
  results: Record<string, unknown>;
  created_at: string;
  completed_at: string | null;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    request_id: string | null;
    details: Record<string, unknown>;
  };
}

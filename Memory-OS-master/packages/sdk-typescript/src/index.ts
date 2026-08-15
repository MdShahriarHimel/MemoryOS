// Official MEMORY OS TypeScript SDK (v0.3).
// Model-independent: callers supply embeddings; the SDK never generates them.

export interface MemoryOSOptions {
  apiKey?: string;
  baseUrl?: string;
  timeoutMs?: number;
}

export class MemoryOSError extends Error {
  constructor(public code: string, message: string, public requestId: string | null) {
    super(message);
  }
}

export class MemoryOS {
  private baseUrl: string;
  private apiKey?: string;
  private timeoutMs: number;

  constructor(opts: MemoryOSOptions = {}) {
    this.baseUrl = opts.baseUrl ?? process.env.MEMORY_OS_API_URL ?? "http://localhost:8000";
    this.apiKey = opts.apiKey ?? process.env.MEMORY_OS_API_KEY;
    this.timeoutMs = opts.timeoutMs ?? 15_000;
  }

  memories = {
    create: (input: {
      content: string; memory_type?: string; embedding?: number[];
      metadata?: Record<string, unknown>; subject?: string; predicate?: string;
      object_value?: string; supersedes?: string[];
    }) => this.req("POST", "/v1/memory", input),
    update: (id: string, input: Record<string, unknown>) =>
      this.req("PATCH", `/v1/memory/${id}`, input),
    delete: (id: string) => this.req("DELETE", `/v1/memory/${id}`),
    search: (input: { query: string; mode?: string; embedding?: number[]; top_k?: number; session_id?: string }) =>
      this.req("POST", "/v1/memory/search", input),
    extract: (input: { content: string; source?: { type: string; id?: string }; store?: boolean }) =>
      this.req("POST", "/v1/memory/extract", input),
    asOf: (input: { as_of: string; subject?: string; predicate?: string }) =>
      this.req("POST", "/v1/memory/as-of", input),
    timeline: (id: string) => this.req("GET", `/v1/memory/${id}/timeline`),
    provenance: (id: string) => this.req("GET", `/v1/memory/${id}/provenance`),
    get: (id: string) => this.req("GET", `/v1/memory/${id}`),
    export: (input?: { user_id?: string }) => this.req("POST", "/v1/memory/export", input ?? {}),
  };

  context = {
    build: (input: { query: string; embedding?: number[]; max_tokens?: number; session_id?: string }) =>
      this.req("POST", "/v1/context", input),
  };

  sessions = {
    create: (input?: { agent_id?: string }) =>
      this.req("POST", "/v1/sessions", input ?? {}),
    list: (params?: { limit?: number; offset?: number; status?: string }) => {
      const q = new URLSearchParams();
      if (params?.limit != null) q.set("limit", String(params.limit));
      if (params?.offset != null) q.set("offset", String(params.offset));
      if (params?.status) q.set("status", params.status);
      const qs = q.toString();
      return this.req("GET", `/v1/sessions${qs ? `?${qs}` : ""}`);
    },
    get: (id: string) => this.req("GET", `/v1/sessions/${id}`),
    events: (id: string) => this.req("GET", `/v1/sessions/${id}/events`),
    appendEvent: (id: string, input: {
      event_type: string; detail: string; latency_ms?: number; payload?: Record<string, unknown>;
    }) => this.req("POST", `/v1/sessions/${id}/events`, input),
  };

  operations = {
    reflection: (staleDays = 90) =>
      this.req("POST", `/v1/operations/reflection?stale_days=${staleDays}`),
    reflectionExecute: (input?: {
      stale_days?: number; dry_run?: boolean; max_actions?: number; action_types?: string[];
    }) => this.req("POST", "/v1/operations/reflection/execute", input ?? { dry_run: true }),
  };

  benchmarks = {
    run: (input?: { name?: string; scale?: number; categories?: string[] }) =>
      this.req("POST", "/v1/benchmarks/run", input ?? {}),
    get: (id: string) => this.req("GET", `/v1/benchmarks/${id}`),
    list: () => this.req("GET", "/v1/benchmarks"),
  };

  private async req(method: string, path: string, body?: unknown, idempotencyKey?: string) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const res = await fetch(`${this.baseUrl}${path}`, {
        method,
        signal: controller.signal,
        headers: {
          "Content-Type": "application/json",
          ...(this.apiKey ? { Authorization: `Bearer ${this.apiKey}` } : {}),
          ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
        },
        body: body ? JSON.stringify(body) : undefined,
      });
      const data = res.status === 204 ? null : await res.json();
      if (!res.ok) {
        const e = data?.error ?? {};
        throw new MemoryOSError(e.code ?? "UNKNOWN", e.message ?? "error", e.request_id ?? null);
      }
      return data;
    } finally {
      clearTimeout(timer);
    }
  }
}

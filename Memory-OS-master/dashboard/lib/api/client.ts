// The ONE API access layer. Components and pages must import from here and never
// call fetch() directly. Handles auth headers, timeouts, request IDs, typed
// responses, and typed errors with the backend's error envelope.

import type {
  AdminStats,
  AgentSession,
  ApiErrorBody,
  Memory,
  Page,
  ReadyState,
  SearchResponse,
  SessionReplayResponse,
  AuditLogEntry,
} from "./types";

const DEFAULT_TIMEOUT_MS = 15_000;

/** Browser calls same-origin proxy (no CORS); server-side uses internal API URL. */
function resolveBaseUrl(): string {
  if (typeof window !== "undefined") return "/api/proxy";
  return (
    process.env.MEMORY_OS_API_URL ??
    process.env.NEXT_PUBLIC_MEMORY_OS_API_URL ??
    "http://localhost:8000"
  );
}

// Access token in memory; refresh token in httpOnly cookie via /api/auth/* routes.

let ACCESS_TOKEN: string | null = null;
let bootstrapPromise: Promise<boolean> | null = null;

export const auth = {
  setAccess(access: string) {
    ACCESS_TOKEN = access;
  },
  get access() {
    return ACCESS_TOKEN;
  },
  async bootstrap(): Promise<boolean> {
    if (ACCESS_TOKEN) return true;
    if (bootstrapPromise) return bootstrapPromise;
    bootstrapPromise = (async () => {
      try {
        const res = await fetch("/api/auth/refresh", { method: "POST", cache: "no-store" });
        if (!res.ok) return false;
        const data = await res.json();
        ACCESS_TOKEN = data.access_token;
        return true;
      } catch {
        return false;
      } finally {
        bootstrapPromise = null;
      }
    })();
    return bootstrapPromise;
  },
  async logout() {
    ACCESS_TOKEN = null;
    await fetch("/api/auth/logout", { method: "POST", cache: "no-store" });
  },
};


export class ApiError extends Error {
  code: string;
  requestId: string | null;
  status: number;
  details: Record<string, unknown>;
  constructor(status: number, body: ApiErrorBody) {
    super(body.error?.message ?? "Request failed");
    this.name = "ApiError";
    this.status = status;
    this.code = body.error?.code ?? "UNKNOWN";
    this.requestId = body.error?.request_id ?? null;
    this.details = body.error?.details ?? {};
  }
}

export class ConnectionError extends Error {
  constructor(message = "Unable to reach MEMORY OS API") {
    super(message);
    this.name = "ConnectionError";
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
  tenantId?: string;
}

function newRequestId(): string {
  return `req_${crypto.randomUUID().replace(/-/g, "").slice(0, 16)}`;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  if (!ACCESS_TOKEN && !opts.tenantId) {
    await auth.bootstrap();
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
  const signal = opts.signal ?? controller.signal;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Request-ID": newRequestId(),
  };
  if (opts.tenantId) headers["X-Tenant-ID"] = opts.tenantId;
  if (ACCESS_TOKEN) headers["Authorization"] = `Bearer ${ACCESS_TOKEN}`;

  let res: Response;
  try {
    res = await fetch(`${resolveBaseUrl()}${path}`, {
      method: opts.method ?? "GET",
      headers,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
      signal,
      cache: "no-store",
    });
  } catch (err) {
    clearTimeout(timeout);
    if ((err as Error).name === "AbortError")
      throw new ConnectionError("Request timed out");
    throw new ConnectionError();
  }
  clearTimeout(timeout);

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      throw new ApiError(res.status, {
        error: { code: "INVALID_JSON", message: "Invalid JSON response", request_id: null, details: {} },
      });
    }
  }

  if (!res.ok) {
    throw new ApiError(res.status, data as ApiErrorBody);
  }
  return data as T;
}

// ---- typed methods --------------------------------------------------------

export const api = {
  // ---- auth (via Next.js routes — refresh in httpOnly cookie) ----
  register: async (body: { email: string; password: string; organization_name: string }) => {
    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new ApiError(res.status, data as ApiErrorBody);
    auth.setAccess(data.access_token);
    return data as { access_token: string; expires_in: number };
  },
  login: async (body: { email: string; password: string }) => {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new ApiError(res.status, data as ApiErrorBody);
    auth.setAccess(data.access_token);
    return data as { access_token: string; expires_in: number };
  },
  logout: () => auth.logout(),
  me: () => request<{ id: string; email: string; role: string; organization_id: string }>("/v1/auth/me"),

  // ---- developer ----
  listApiKeys: () =>
    request<Array<{ id: string; name: string; prefix: string; scopes: string[]; environment: string; revoked: boolean; last_used_at: string | null; created_at: string }>>(
      "/v1/api-keys",
    ),
  createApiKey: (body: { name: string; scopes: string[]; environment?: string }) =>
    request<{ id: string; name: string; prefix: string; scopes: string[]; secret: string; created_at: string }>(
      "/v1/api-keys",
      { method: "POST", body },
    ),
  revokeApiKey: (id: string) => request<void>(`/v1/api-keys/${id}`, { method: "DELETE" }),
  rotateApiKey: (id: string) =>
    request<{ secret: string }>(`/v1/api-keys/${id}/rotate`, { method: "POST" }),

  listWebhooks: () =>
    request<Array<{ id: string; url: string; events: string[]; status: string; created_at: string }>>(
      "/v1/webhooks",
    ),
  createWebhook: (body: { url: string; events: string[] }) =>
    request<{ id: string; url: string; events: string[]; secret: string; created_at: string }>(
      "/v1/webhooks",
      { method: "POST", body },
    ),
  deleteWebhook: (id: string) => request<void>(`/v1/webhooks/${id}`, { method: "DELETE" }),

  // ---- analytics ----
  analyticsSummary: () =>
    request<{ memory_created_total: number; retrieval_total: number; api_request_total: number }>(
      "/v1/analytics/summary",
    ),
  analyticsSeries: (kind: string, days = 14) =>
    request<{ kind: string; days: number; series: { date: string; value: number }[] }>(
      `/v1/analytics/series?kind=${encodeURIComponent(kind)}&days=${days}`,
    ),

  // ---- graph ----
  getGraph: (depth = 1, limit = 200) =>
    request<{ nodes: { id: string; key: string; entity_type: string; label: string }[]; edges: { source_id: string; target_id: string; rel_type: string; confidence: number }[] }>(
      `/v1/graph?depth=${depth}&limit=${limit}`,
    ),

  getReady: (tenantId?: string) => request<ReadyState>("/v1/ready", { tenantId }),

  getHealth: () => request<import("./types").HealthState>("/v1/health"),

  getStats: (tenantId?: string) =>
    request<AdminStats>("/v1/admin/stats", { tenantId }),

  listMemories: (params: { limit?: number; offset?: number; tenantId?: string } = {}) =>
    request<Page<Memory>>(
      `/v1/memory?limit=${params.limit ?? 25}&offset=${params.offset ?? 0}`,
      { tenantId: params.tenantId },
    ),

  getMemory: (id: string, tenantId?: string) =>
    request<Memory>(`/v1/memory/${id}`, { tenantId }),

  createMemory: (payload: Record<string, unknown>, tenantId?: string) =>
    request<Memory>("/v1/memory", { method: "POST", body: payload, tenantId }),

  deleteMemory: (id: string, tenantId?: string) =>
    request<void>(`/v1/memory/${id}`, { method: "DELETE", tenantId }),

  searchMemories: (
    payload: {
      query: string;
      mode?: string;
      embedding?: number[];
      top_k?: number;
      memory_type?: string;
      min_confidence?: number;
      max_graph_hops?: number;
    },
    tenantId?: string,
  ) =>
    request<SearchResponse>("/v1/memory/search", {
      method: "POST",
      body: payload,
      tenantId,
    }),

  buildContext: (payload: { query: string; embedding?: number[]; max_tokens?: number }, tenantId?: string) =>
    request<import("./types").ContextBuildResponse>("/v1/context", {
      method: "POST",
      body: payload,
      tenantId,
    }),

  extractMemory: (payload: { content: string; store?: boolean }, tenantId?: string) =>
    request<{ facts: Array<Record<string, unknown>>; method: string; stored_memory_ids: string[] }>(
      "/v1/memory/extract",
      { method: "POST", body: payload, tenantId },
    ),

  getTimeline: (memoryId: string, tenantId?: string) =>
    request<import("./types").TimelineResponse>(`/v1/memory/${memoryId}/timeline`, { tenantId }),

  getProvenance: (memoryId: string, tenantId?: string) =>
    request<import("./types").ProvenanceResponse>(`/v1/memory/${memoryId}/provenance`, { tenantId }),

  listSessions: (params: { limit?: number; offset?: number; status?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.limit != null) q.set("limit", String(params.limit));
    if (params.offset != null) q.set("offset", String(params.offset));
    if (params.status) q.set("status", params.status);
    const qs = q.toString();
    return request<Page<AgentSession>>(`/v1/sessions${qs ? `?${qs}` : ""}`);
  },

  getSession: (sessionId: string) =>
    request<AgentSession>(`/v1/sessions/${sessionId}`),

  getSessionEvents: (sessionId: string) =>
    request<SessionReplayResponse>(`/v1/sessions/${sessionId}/events`),

  runReflection: (staleDays = 90) =>
    request<{ scanned: number; summary: Record<string, number>; actions: Array<Record<string, unknown>> }>(
      `/v1/operations/reflection?stale_days=${staleDays}`,
      { method: "POST" },
    ),

  executeReflection: (body: {
    stale_days?: number;
    dry_run?: boolean;
    max_actions?: number;
    action_types?: string[];
  } = {}) =>
    request<{
      scanned: number;
      summary: Record<string, number>;
      dry_run: boolean;
      planned: Array<Record<string, unknown>>;
      results: Array<{ action: string; memory_ids: string[]; result: string; detail: string; reason: string }>;
    }>("/v1/operations/reflection/execute", { method: "POST", body }),

  listAuditLogs: (params: { limit?: number; offset?: number; action?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.limit != null) q.set("limit", String(params.limit));
    if (params.offset != null) q.set("offset", String(params.offset));
    if (params.action) q.set("action", params.action);
    const qs = q.toString();
    return request<AuditLogEntry[]>(`/v1/audit/logs${qs ? `?${qs}` : ""}`);
  },

  runBenchmark: (payload: { name: string; scale?: number; categories?: string[] }) =>
    request<import("./types").BenchmarkRunOut>("/v1/benchmarks/run", { method: "POST", body: payload }),

  listBenchmarkRuns: () =>
    request<import("./types").BenchmarkRunOut[]>("/v1/benchmarks"),

  getDeveloperPortal: () =>
    request<{
      docs: string;
      redoc: string;
      openapi: string;
      sdks: Record<string, string>;
      cli: string;
      authentication: Record<string, string>;
      operations: Record<string, string>;
      v03?: Record<string, string>;
      observability: Record<string, string>;
    }>("/developer"),
};

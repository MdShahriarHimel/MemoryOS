"use client";

import { useState } from "react";
import { ChevronRight, Network, Search, Sparkles, Zap } from "lucide-react";
import { api, ApiError, ConnectionError } from "@/lib/api/client";
import type { SearchResponse, SearchResultItem } from "@/lib/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "@/components/ui/states";
import { cn, formatPercent } from "@/lib/utils";

const MODES = ["hybrid", "vector", "keyword", "graph", "temporal"] as const;

function TraceBar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[10px]">
        <span className="text-[var(--text-muted)]">{label}</span>
        <span className="mono text-[var(--text-secondary)]">{value}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-[var(--surface-2)]">
        <div
          className="h-full rounded-full transition-all duration-500 ease-out"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  );
}

function MemoryDetail({ item, onTimeline }: { item: SearchResultItem; onTimeline: (id: string) => void }) {
  const m = item.memory;
  return (
    <div className="space-y-4 animate-fade-in">
      <div>
        <p className="text-sm leading-relaxed text-[var(--text-primary)]">{m.content}</p>
        <div className="mono mt-2 text-lg font-semibold text-[var(--accent-cyan)]">{item.score.toFixed(4)}</div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <Badge tone="blue">{m.memory_type}</Badge>
        <Badge tone="purple">v{m.version}</Badge>
        <Badge tone="cyan">conf {formatPercent(m.confidence)}</Badge>
        {m.subject && <Badge>{m.subject} · {m.predicate}</Badge>}
      </div>
      {item.channels.length > 0 && (
        <div>
          <p className="mb-1.5 text-[10px] uppercase tracking-wide text-[var(--text-muted)]">Channels</p>
          <div className="flex flex-wrap gap-1">
            {item.channels.map((c) => (
              <Badge key={c} tone="purple">{c}</Badge>
            ))}
          </div>
        </div>
      )}
      {m.quality && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)]/50 p-3">
          <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)]">Quality score</p>
          <p className="metric mt-1 text-xl">{formatPercent(m.quality.score)}</p>
        </div>
      )}
      <Button variant="secondary" size="sm" onClick={() => onTimeline(m.id)}>
        View timeline
        <ChevronRight className="h-3.5 w-3.5" />
      </Button>
    </div>
  );
}

export default function MemoryExplorerPage() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<(typeof MODES)[number]>("hybrid");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [selected, setSelected] = useState<SearchResultItem | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "error" | "unavailable">("idle");
  const [errMsg, setErrMsg] = useState("");
  const [reqId, setReqId] = useState<string | null>(null);

  async function run() {
    if (!query.trim()) return;
    setState("loading");
    setSelected(null);
    try {
      const res = await api.searchMemories({ query, mode, top_k: 12 });
      setData(res);
      if (res.results.length > 0) setSelected(res.results[0]);
      setState("idle");
    } catch (e) {
      if (e instanceof ConnectionError) return setState("unavailable");
      if (e instanceof ApiError) {
        setErrMsg(e.message);
        setReqId(e.requestId);
      } else setErrMsg("Search failed.");
      setState("error");
    }
  }

  const trace = data?.retrieval_trace;
  const maxCandidates = trace
    ? Math.max(trace.vector_candidates, trace.keyword_candidates, trace.graph_candidates, 1)
    : 1;

  return (
    <div className="mx-auto max-w-6xl animate-fade-in">
      <PageHeader
        title="Memory Explorer"
        description="Hybrid retrieval with live trace — vector, keyword, graph, and temporal channels."
      />

      <Card className="overflow-hidden p-0">
        <div className="border-b border-[var(--border)] bg-gradient-to-r from-[var(--accent-blue)]/5 to-[var(--accent-purple)]/5 p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-[var(--surface-2)] p-2.5 text-[var(--accent-blue)]">
              <Search className="h-5 w-5" />
            </div>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && run()}
              placeholder="What does the user prefer? Where do they live?"
              className="flex-1 bg-transparent text-base outline-none placeholder:text-[var(--text-muted)]"
              aria-label="Search query"
            />
            <Button onClick={run} loading={state === "loading"}>
              <Zap className="h-3.5 w-3.5" />
              Search
            </Button>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {MODES.map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={cn(
                  "rounded-lg border px-3 py-1.5 text-xs font-medium capitalize transition-all duration-200",
                  mode === m
                    ? "border-[var(--accent-blue)] bg-[var(--accent-blue)]/15 text-[var(--text-primary)] shadow-sm shadow-blue-500/10"
                    : "border-[var(--border)] text-[var(--text-secondary)] hover:border-[var(--border-strong)] hover:bg-[var(--surface-2)]",
                )}
              >
                {m}
              </button>
            ))}
          </div>
          {(mode === "vector" || mode === "hybrid") && (
            <p className="mt-3 text-[11px] text-[var(--text-muted)]">
              Vector channels require a client-supplied embedding. Keyword + graph still apply.
            </p>
          )}
        </div>
      </Card>

      <div className="mt-6 grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-3 space-y-4">
          {state === "loading" && <LoadingState label="Retrieving" />}
          {state === "unavailable" && <UnavailableState onRetry={run} />}
          {state === "error" && <ErrorState message={errMsg} requestId={reqId} onRetry={run} />}
          {state === "idle" && data && (
            <>
              {trace && (
                <Card className="p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                      <Network className="h-3.5 w-3.5" />
                      Retrieval trace
                    </h3>
                    <span className="mono text-xs text-[var(--accent-cyan)]">{trace.latency_ms}ms</span>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <TraceBar label="Vector" value={trace.vector_candidates} max={maxCandidates} color="var(--accent-blue)" />
                    <TraceBar label="Keyword" value={trace.keyword_candidates} max={maxCandidates} color="var(--accent-purple)" />
                    <TraceBar label="Graph" value={trace.graph_candidates} max={maxCandidates} color="var(--accent-cyan)" />
                    <TraceBar label="Final" value={trace.final_results} max={trace.merged_candidates || 1} color="var(--ok)" />
                  </div>
                </Card>
              )}
              {data.results.length === 0 ? (
                <EmptyState title="No memories found" hint="Try a different query or mode." />
              ) : (
                <ul className="space-y-2">
                  {data.results.map((r, i) => (
                    <li
                      key={r.memory.id}
                      className={cn(
                        "cursor-pointer rounded-[var(--radius)] border p-4 transition-all duration-200 opacity-0 animate-slide-up",
                        selected?.memory.id === r.memory.id
                          ? "border-[var(--accent-blue)]/50 bg-[var(--accent-blue)]/5 shadow-[var(--glow-blue)]"
                          : "border-[var(--border)] bg-[var(--surface-1)]/80 hover:border-[var(--border-strong)] hover:bg-[var(--surface-2)]/40",
                      )}
                      style={{ animationDelay: `${i * 40}ms`, animationFillMode: "forwards" }}
                      onClick={() => setSelected(r)}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-sm text-[var(--text-primary)] line-clamp-2">{r.memory.content}</p>
                        <span className="mono shrink-0 text-[11px] text-[var(--accent-cyan)]">{r.score.toFixed(3)}</span>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        <Badge tone="blue">{r.memory.memory_type}</Badge>
                        {r.channels.map((c) => (
                          <Badge key={c} tone="purple">{c}</Badge>
                        ))}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
          {state === "idle" && !data && (
            <EmptyState title="Search your memory layer" hint="Enter a query to retrieve context." icon={Search} />
          )}
        </div>

        <div className="lg:col-span-2">
          <Card className="sticky top-20 min-h-[280px] p-4">
            <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-[var(--text-secondary)]">
              <Sparkles className="h-4 w-4 text-[var(--accent-purple)]" />
              Memory detail
            </h3>
            {selected ? (
              <MemoryDetail
                item={selected}
                onTimeline={(id) => window.location.href = `/timeline?id=${id}`}
              />
            ) : (
              <p className="py-12 text-center text-sm text-[var(--text-muted)]">
                Select a result to inspect provenance, quality, and channels.
              </p>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

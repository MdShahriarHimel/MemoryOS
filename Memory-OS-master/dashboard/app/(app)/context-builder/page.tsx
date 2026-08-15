"use client";

import { useState } from "react";
import { BookOpen, GitBranch, Layers, Sparkles, Zap } from "lucide-react";
import { api, ApiError, ConnectionError } from "@/lib/api/client";
import type { ContextBuildResponse } from "@/lib/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "@/components/ui/states";

export default function ContextBuilderPage() {
  const [query, setQuery] = useState("");
  const [data, setData] = useState<ContextBuildResponse | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "error" | "unavailable">("idle");
  const [errMsg, setErrMsg] = useState("");

  async function build() {
    if (!query.trim()) return;
    setState("loading");
    try {
      const res = await api.buildContext({ query, max_tokens: 4000 });
      setData(res);
      setState("idle");
    } catch (e) {
      if (e instanceof ConnectionError) setState("unavailable");
      else if (e instanceof ApiError) setErrMsg(e.message);
      else setErrMsg("Context build failed.");
      setState("error");
    }
  }

  return (
    <div className="mx-auto max-w-6xl animate-fade-in">
      <PageHeader
        title="Context Builder"
        description="Assemble agent-ready context: memories, truths, entities, conflicts, and provenance — no LLM reasoning inside MEMORY OS."
      />

      <Card className="overflow-hidden">
        <div className="border-b border-[var(--border)] bg-gradient-to-r from-[var(--accent-purple)]/10 to-[var(--accent-cyan)]/5 p-5">
          <div className="flex gap-3">
            <div className="rounded-lg bg-[var(--surface-2)] p-2.5 text-[var(--accent-purple)]">
              <Sparkles className="h-5 w-5" />
            </div>
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              rows={2}
              placeholder="What context does the agent need before responding?"
              className="flex-1 resize-none bg-transparent text-sm outline-none placeholder:text-[var(--text-muted)]"
            />
            <Button onClick={build} loading={state === "loading"} className="self-end">
              <Zap className="h-3.5 w-3.5" />
              Build
            </Button>
          </div>
        </div>
      </Card>

      <div className="mt-6">
        {state === "loading" && <LoadingState label="Building context" />}
        {state === "unavailable" && <UnavailableState onRetry={build} />}
        {state === "error" && <ErrorState message={errMsg} onRetry={build} />}
        {state === "idle" && !data && (
          <EmptyState title="Build agent context" hint="Enter a query to assemble memories, truths, and provenance." icon={Sparkles} />
        )}
        {state === "idle" && data && (
          <div className="grid gap-4 lg:grid-cols-2 animate-slide-up">
            <Card>
              <CardHeader>
                <h3 className="flex items-center gap-2 text-sm font-semibold">
                  <Layers className="h-4 w-4 text-[var(--accent-blue)]" />
                  Memories ({data.memories.length})
                </h3>
              </CardHeader>
              <CardBody className="max-h-64 space-y-2 overflow-y-auto pt-0">
                {data.memories.map((m) => (
                  <div key={m.id} className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)]/40 p-3 text-sm">
                    {m.content}
                    <div className="mt-2 flex gap-1">
                      <Badge tone="blue">{m.memory_type}</Badge>
                      {m.subject && <Badge tone="cyan">{m.subject}</Badge>}
                    </div>
                  </div>
                ))}
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <h3 className="flex items-center gap-2 text-sm font-semibold">
                  <BookOpen className="h-4 w-4 text-[var(--accent-cyan)]" />
                  Current truths ({data.current_truths.length})
                </h3>
              </CardHeader>
              <CardBody className="space-y-2 pt-0">
                {data.current_truths.length === 0 ? (
                  <p className="text-sm text-[var(--text-muted)]">No resolved truths in scope.</p>
                ) : (
                  data.current_truths.map((t, i) => (
                    <div key={i} className="rounded-lg border border-[var(--border)] p-3 text-sm">
                      <span className="text-[var(--text-muted)]">{String(t.subject)} · {String(t.predicate)}</span>
                      <p className="mt-1 font-medium text-[var(--accent-cyan)]">{String(t.current_value)}</p>
                    </div>
                  ))
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <h3 className="flex items-center gap-2 text-sm font-semibold">
                  <GitBranch className="h-4 w-4 text-[var(--accent-purple)]" />
                  Entities & relationships
                </h3>
              </CardHeader>
              <CardBody className="pt-0">
                <p className="text-sm text-[var(--text-secondary)]">
                  {data.entities.length} entities · {data.relationships.length} relationships
                </p>
                {data.conflicts.length > 0 && (
                  <p className="mt-2 text-xs text-[var(--warn)]">{data.conflicts.length} potential conflicts flagged</p>
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <h3 className="text-sm font-semibold">Retrieval trace</h3>
              </CardHeader>
              <CardBody className="mono space-y-1 pt-0 text-xs text-[var(--text-secondary)]">
                <p>vector: {data.retrieval_trace.vector_candidates}</p>
                <p>keyword: {data.retrieval_trace.keyword_candidates}</p>
                <p>graph: {data.retrieval_trace.graph_candidates}</p>
                <p className="text-[var(--accent-cyan)]">{data.retrieval_trace.latency_ms}ms</p>
              </CardBody>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}

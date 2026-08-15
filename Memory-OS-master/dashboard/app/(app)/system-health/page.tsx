"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity, Boxes, Database, GitMerge, Layers, RefreshCw, Server, ShieldCheck, Users, Zap,
} from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { MetricCard } from "@/components/ui/metric-card";
import { PageHeader } from "@/components/ui/page-header";
import { api, ConnectionError } from "@/lib/api/client";
import { ErrorState, LoadingState, UnavailableState } from "@/components/ui/states";
import { cn, formatNumber, formatPercent } from "@/lib/utils";

const COMPONENT_LABEL: Record<string, string> = {
  postgres: "Database",
  redis: "Redis",
  neo4j: "Neo4j",
  opensearch: "OpenSearch",
};

function statusTone(state: string): "ok" | "warn" | "default" {
  if (state === "operational") return "ok";
  if (state === "not_configured") return "default";
  return "warn";
}

function overallTone(status: string): "ok" | "warn" | "default" {
  if (status === "operational") return "ok";
  if (status === "degraded") return "warn";
  return "default";
}

export default function SystemHealthPage() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api.getHealth(),
    refetchInterval: 30_000,
  });
  const ready = useQuery({
    queryKey: ["ready"],
    queryFn: () => api.getReady(),
    refetchInterval: 30_000,
  });
  const stats = useQuery({
    queryKey: ["stats"],
    queryFn: () => api.getStats(),
    refetchInterval: 30_000,
  });
  const analytics = useQuery({
    queryKey: ["analytics-summary"],
    queryFn: () => api.analyticsSummary(),
    refetchInterval: 60_000,
    retry: false,
  });

  const connErr =
    health.error instanceof ConnectionError ||
    ready.error instanceof ConnectionError ||
    stats.error instanceof ConnectionError;

  function refreshAll() {
    health.refetch();
    ready.refetch();
    stats.refetch();
    analytics.refetch();
  }

  const overall = ready.data?.status ?? health.data?.status ?? "unknown";
  const isLoading = health.isLoading || ready.isLoading;

  return (
    <div className="mx-auto max-w-6xl animate-fade-in">
      <PageHeader
        title="System Health"
        description="Live readiness, dependency status, and tenant-level operational metrics."
        action={
          <div className="flex items-center gap-2">
            {!isLoading && (
              <Badge tone={overallTone(overall)} className="capitalize">{overall}</Badge>
            )}
            <Button variant="secondary" size="sm" onClick={refreshAll}>
              <RefreshCw className="h-3.5 w-3.5" />
              Refresh
            </Button>
          </div>
        }
      />

      {connErr ? (
        <Card><UnavailableState onRetry={refreshAll} /></Card>
      ) : isLoading ? (
        <LoadingState label="Checking system health" />
      ) : (
        <>
          <Card className="mb-6 overflow-hidden" glow={overall === "operational" ? "cyan" : undefined}>
            <div className="border-b border-[var(--border)] bg-gradient-to-r from-[var(--accent-cyan)]/10 to-[var(--accent-blue)]/5 px-5 py-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className={cn(
                    "rounded-xl border p-3",
                    overall === "operational"
                      ? "border-[var(--ok)]/30 bg-[var(--ok)]/10 text-[var(--ok)]"
                      : "border-[var(--warn)]/30 bg-[var(--warn)]/10 text-[var(--warn)]",
                  )}>
                    <Server className="h-6 w-6" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold capitalize text-[var(--text-primary)]">
                      {overall === "operational" ? "All core systems operational" : `Status: ${overall}`}
                    </p>
                    {health.data?.time && (
                      <p className="text-[11px] text-[var(--text-muted)]">
                        Last ping {new Date(health.data.time).toLocaleString()}
                      </p>
                    )}
                  </div>
                </div>
                <Link href="/developer">
                  <Button variant="ghost" size="sm">Developer Portal →</Button>
                </Link>
              </div>
            </div>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card interactive className="opacity-0 animate-slide-up" style={{ animationFillMode: "forwards" }}>
              <CardHeader>
                <h2 className="flex items-center gap-2 text-sm font-semibold">
                  <Zap className="h-4 w-4 text-[var(--accent-cyan)]" />
                  Components
                </h2>
              </CardHeader>
              <CardBody className="pt-0">
                {ready.error ? (
                  <ErrorState message="Could not load readiness." onRetry={() => ready.refetch()} />
                ) : ready.data ? (
                  <ul className="space-y-2">
                    {Object.entries(ready.data.components).map(([name, state]) => (
                      <li
                        key={name}
                        className="flex items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--surface-2)]/40 px-3 py-2.5 text-sm"
                      >
                        <span className="text-[var(--text-secondary)]">
                          {COMPONENT_LABEL[name] ?? name}
                        </span>
                        <Badge tone={statusTone(state)}>{state.replace(/_/g, " ")}</Badge>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </CardBody>
            </Card>

            <Card interactive className="opacity-0 animate-slide-up stagger-2" style={{ animationFillMode: "forwards" }}>
              <CardHeader>
                <h2 className="flex items-center gap-2 text-sm font-semibold">
                  <Activity className="h-4 w-4 text-[var(--accent-purple)]" />
                  Analytics counters
                </h2>
              </CardHeader>
              <CardBody className="pt-0">
                {analytics.isError ? (
                  <p className="py-6 text-center text-xs text-[var(--text-muted)]">
                    Analytics pipeline not reporting yet — counters unavailable.
                  </p>
                ) : analytics.isLoading ? (
                  <LoadingState label="Loading analytics" />
                ) : analytics.data ? (
                  <ul className="space-y-2">
                    {[
                      { label: "Memories created", value: analytics.data.memory_created_total },
                      { label: "Retrievals", value: analytics.data.retrieval_total },
                      { label: "API requests", value: analytics.data.api_request_total },
                    ].map((row) => (
                      <li
                        key={row.label}
                        className="flex items-center justify-between rounded-lg bg-[var(--surface-2)]/40 px-3 py-2 text-sm"
                      >
                        <span className="text-[var(--text-secondary)]">{row.label}</span>
                        <span className="mono font-medium">{formatNumber(row.value)}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </CardBody>
            </Card>
          </div>

          {stats.data && (
            <section className="mt-8">
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--text-muted)]">
                Tenant metrics
              </h2>
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
                <MetricCard label="Total Memories" value={formatNumber(stats.data.total_memories)} icon={Layers} tone="blue" delay={0} />
                <MetricCard label="Active Agents" value={formatNumber(stats.data.active_agents)} icon={Boxes} tone="purple" delay={1} />
                <MetricCard label="Avg Confidence" value={formatPercent(stats.data.avg_confidence)} icon={ShieldCheck} tone="cyan" delay={2} />
                <MetricCard label="Open Conflicts" value={formatNumber(stats.data.open_conflicts)} icon={GitMerge} tone="ok" delay={3} />
                <MetricCard label="Active Sessions" value={formatNumber(stats.data.active_sessions)} icon={Users} tone="purple" delay={4} />
                <MetricCard
                  label="Retrievals (24h)"
                  value={stats.data.retrievals_24h === null ? "—" : formatNumber(stats.data.retrievals_24h)}
                  icon={Database}
                  tone="blue"
                  delay={5}
                  unavailable={stats.data.retrievals_24h === null}
                />
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

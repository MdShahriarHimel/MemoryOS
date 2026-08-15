"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Boxes, Database, GitMerge, Layers, ShieldCheck, Sparkles, Users, Zap } from "lucide-react";
import Link from "next/link";
import { MetricCard } from "@/components/ui/metric-card";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api, ConnectionError } from "@/lib/api/client";
import { ErrorState, LoadingState, Skeleton, UnavailableState } from "@/components/ui/states";
import { formatNumber, formatPercent } from "@/lib/utils";

const QUICK_ACTIONS = [
  { label: "Search memories", href: "/memory-explorer", icon: Database, desc: "Hybrid retrieval" },
  { label: "Build context", href: "/context-builder", icon: Sparkles, desc: "Agent-ready payload" },
  { label: "View graph", href: "/knowledge-graph", icon: GitMerge, desc: "Entity relationships" },
];

export default function DashboardPage() {
  const stats = useQuery({ queryKey: ["stats"], queryFn: () => api.getStats() });
  const ready = useQuery({ queryKey: ["ready"], queryFn: () => api.getReady() });
  const connErr = stats.error instanceof ConnectionError || ready.error instanceof ConnectionError;
  const healthy = ready.data?.status === "operational";

  return (
    <div className="mx-auto max-w-6xl animate-fade-in">
      <PageHeader
        title={healthy ? "Your memory infrastructure is healthy" : "Memory infrastructure"}
        description="Deterministic memory core, hybrid retrieval, temporal truth, and provenance — model-independent."
        action={
          <Link href="/memory-explorer">
            <Button size="sm">
              Explore memories
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        }
      />

      {connErr ? (
        <Card><UnavailableState onRetry={() => { stats.refetch(); ready.refetch(); }} /></Card>
      ) : stats.isLoading ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[120px] rounded-[var(--radius)]" />
          ))}
        </div>
      ) : stats.error ? (
        <Card><ErrorState message="Could not load dashboard metrics." onRetry={() => stats.refetch()} /></Card>
      ) : (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
          <MetricCard label="Total Memories" value={formatNumber(stats.data!.total_memories)} icon={Layers} tone="blue" delay={0} />
          <MetricCard label="Active Agents" value={formatNumber(stats.data!.active_agents)} icon={Boxes} tone="purple" delay={1} />
          <MetricCard label="Avg Confidence" value={formatPercent(stats.data!.avg_confidence)} icon={ShieldCheck} tone="cyan" delay={2} />
          <MetricCard label="Open Conflicts" value={formatNumber(stats.data!.open_conflicts)} icon={GitMerge} tone="ok" delay={3} />
          <MetricCard label="Active Sessions" value={formatNumber(stats.data!.active_sessions)} icon={Users} tone="purple" delay={4} />
          <MetricCard
            label="Retrievals (24h)"
            value={stats.data!.retrievals_24h === null ? "—" : formatNumber(stats.data!.retrievals_24h)}
            icon={Database}
            tone="blue"
            delay={5}
            unavailable={stats.data!.retrievals_24h === null}
          />
        </div>
      )}

      <section className="mt-8 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1 opacity-0 animate-slide-up stagger-3" style={{ animationFillMode: "forwards" }}>
          <CardHeader>
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <Zap className="h-4 w-4 text-[var(--accent-cyan)]" />
              Quick actions
            </h2>
          </CardHeader>
          <CardBody className="space-y-2 pt-0">
            {QUICK_ACTIONS.map((a) => {
              const Icon = a.icon;
              return (
                <Link
                  key={a.href}
                  href={a.href}
                  className="group flex items-center gap-3 rounded-lg border border-transparent p-3 transition-all hover:border-[var(--border)] hover:bg-[var(--surface-2)]/60"
                >
                  <div className="rounded-lg bg-[var(--surface-2)] p-2 text-[var(--accent-blue)] transition-colors group-hover:bg-[var(--accent-blue)]/10">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-[var(--text-primary)]">{a.label}</p>
                    <p className="text-[11px] text-[var(--text-muted)]">{a.desc}</p>
                  </div>
                  <ArrowRight className="h-4 w-4 shrink-0 text-[var(--text-muted)] opacity-0 transition-all group-hover:translate-x-0.5 group-hover:opacity-100" />
                </Link>
              );
            })}
          </CardBody>
        </Card>

        <Card className="lg:col-span-1 opacity-0 animate-slide-up stagger-4" style={{ animationFillMode: "forwards" }}>
          <CardHeader>
            <h2 className="text-sm font-semibold">System health</h2>
          </CardHeader>
          <CardBody className="pt-0">
            {ready.isLoading ? (
              <LoadingState label="Checking components" />
            ) : ready.data ? (
              <ul className="space-y-2">
                {Object.entries(ready.data.components).map(([name, state]) => (
                  <li key={name} className="flex items-center justify-between rounded-lg bg-[var(--surface-2)]/40 px-3 py-2 text-sm">
                    <span className="capitalize text-[var(--text-secondary)]">{name}</span>
                    <Badge tone={state === "operational" ? "ok" : state === "not_configured" ? "default" : "warn"}>
                      {state.replace(/_/g, " ")}
                    </Badge>
                  </li>
                ))}
              </ul>
            ) : (
              <UnavailableState onRetry={() => ready.refetch()} />
            )}
          </CardBody>
        </Card>

        <Card className="lg:col-span-1 opacity-0 animate-slide-up stagger-5" style={{ animationFillMode: "forwards" }}>
          <CardHeader>
            <h2 className="text-sm font-semibold">Recent conflicts</h2>
          </CardHeader>
          <CardBody className="pt-0">
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <div className="mb-3 rounded-full border border-[var(--ok)]/30 bg-[var(--ok)]/10 p-3">
                <ShieldCheck className="h-5 w-5 text-[var(--ok)]" />
              </div>
              <p className="text-sm text-[var(--text-secondary)]">No unresolved conflicts</p>
              <p className="mt-1 text-xs text-[var(--text-muted)]">Your memory layer is consistent</p>
            </div>
          </CardBody>
        </Card>
      </section>
    </div>
  );
}

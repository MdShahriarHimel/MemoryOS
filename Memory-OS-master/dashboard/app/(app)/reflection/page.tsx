"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GitBranch, Play, ScanSearch, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { MetricCard } from "@/components/ui/metric-card";
import { PageHeader } from "@/components/ui/page-header";
import { api, ApiError } from "@/lib/api/client";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { cn, formatNumber } from "@/lib/utils";

const ACTION_TONE: Record<string, "blue" | "purple" | "cyan" | "warn" | "ok" | "default"> = {
  merge: "purple",
  archive: "default",
  review_conflict: "warn",
  fix_provenance: "cyan",
};

const RESULT_TONE: Record<string, "ok" | "warn" | "default" | "cyan"> = {
  applied: "ok",
  dry_run: "cyan",
  skipped: "default",
};

export default function ReflectionPage() {
  const qc = useQueryClient();
  const [staleDays, setStaleDays] = useState(90);
  const [dryRun, setDryRun] = useState(true);
  const [executeResult, setExecuteResult] = useState<Awaited<ReturnType<typeof api.executeReflection>> | null>(null);
  const [err, setErr] = useState("");

  const plan = useQuery({
    queryKey: ["reflection-plan", staleDays],
    queryFn: () => api.runReflection(staleDays),
    enabled: false,
  });

  const execute = useMutation({
    mutationFn: () => api.executeReflection({ stale_days: staleDays, dry_run: dryRun }),
    onSuccess: (data) => {
      setExecuteResult(data);
      setErr("");
      if (!data.dry_run) {
        qc.invalidateQueries({ queryKey: ["stats"] });
        qc.invalidateQueries({ queryKey: ["reflection-plan"] });
      }
    },
    onError: (e) => {
      setExecuteResult(null);
      setErr(e instanceof ApiError ? e.message : "Reflection failed.");
    },
  });

  async function scan() {
    setErr("");
    setExecuteResult(null);
    await plan.refetch();
  }

  const summary = plan.data?.summary ?? executeResult?.summary;
  const actions = plan.data?.actions ?? executeResult?.planned ?? [];

  return (
    <div className="mx-auto max-w-5xl animate-fade-in">
      <PageHeader
        title="Reflection"
        description="Scan memory health, review consolidation actions, and apply merges, archives, and conflict triage explicitly."
        action={<Badge tone="purple">v0.4 execution</Badge>}
      />

      <Card className="mb-6 overflow-hidden">
        <div className="border-b border-[var(--border)] bg-gradient-to-r from-[var(--accent-purple)]/10 to-transparent px-5 py-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <ScanSearch className="h-4 w-4 text-[var(--accent-purple)]" />
            Consolidation scan
          </h2>
        </div>
        <CardBody className="flex flex-wrap items-end gap-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">Stale threshold (days)</label>
            <input
              type="number"
              min={1}
              max={365}
              value={staleDays}
              onChange={(e) => setStaleDays(Number(e.target.value))}
              className="w-28 rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm outline-none focus:border-[var(--accent-purple)]"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
            <input
              type="checkbox"
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
              className="accent-[var(--accent-purple)]"
            />
            Dry run (preview only)
          </label>
          <Button variant="secondary" onClick={scan} loading={plan.isFetching}>
            <ScanSearch className="h-4 w-4" />
            Scan
          </Button>
          <Button
            onClick={() => execute.mutate()}
            loading={execute.isPending}
            disabled={!plan.data && !dryRun}
          >
            <Play className="h-4 w-4" />
            {dryRun ? "Preview execute" : "Apply plan"}
          </Button>
        </CardBody>
      </Card>

      {plan.isFetching && <LoadingState label="Scanning memories" />}
      {err && <ErrorState message={err} onRetry={() => execute.mutate()} />}
      {plan.error && !plan.isFetching && (
        <ErrorState message="Could not run reflection scan." onRetry={scan} />
      )}

      {summary && (
        <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Object.entries(summary).map(([key, val], i) => (
            <MetricCard
              key={key}
              label={key.replace(/_/g, " ")}
              value={formatNumber(val)}
              icon={GitBranch}
              tone={ACTION_TONE[key] === "warn" ? "ok" : (ACTION_TONE[key] as "blue" | "purple" | "cyan" | "ok") ?? "blue"}
              delay={i}
            />
          ))}
        </div>
      )}

      {executeResult && (
        <Card className="mb-6 border-[var(--accent-cyan)]/30">
          <CardHeader>
            <h2 className="text-sm font-semibold">
              Execution results {executeResult.dry_run ? "(dry run)" : "(applied)"}
            </h2>
          </CardHeader>
          <CardBody className="max-h-48 space-y-2 overflow-y-auto pt-0">
            {executeResult.results.map((r, i) => (
              <div key={i} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-[var(--surface-2)]/40 px-3 py-2 text-xs">
                <span className="capitalize text-[var(--text-secondary)]">{r.action.replace(/_/g, " ")}</span>
                <Badge tone={RESULT_TONE[r.result] ?? "default"}>{r.result}</Badge>
                <span className="w-full text-[var(--text-muted)]">{r.detail}</span>
              </div>
            ))}
          </CardBody>
        </Card>
      )}

      {actions.length > 0 ? (
        <Card interactive className="overflow-hidden">
          <CardHeader>
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <ShieldAlert className="h-4 w-4 text-[var(--warn)]" />
              Planned actions ({actions.length})
            </h2>
          </CardHeader>
          <CardBody className="max-h-96 space-y-2 overflow-y-auto pt-0">
            {actions.map((a, i) => (
              <div
                key={i}
                className={cn(
                  "rounded-lg border border-[var(--border)] bg-[var(--surface-2)]/30 p-3 opacity-0 animate-slide-up",
                )}
                style={{ animationDelay: `${Math.min(i, 10) * 40}ms`, animationFillMode: "forwards" }}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={ACTION_TONE[String(a.action)] ?? "default"}>{String(a.action)}</Badge>
                  <span className="text-[11px] text-[var(--text-muted)]">priority {Number(a.priority).toFixed(2)}</span>
                </div>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">{String(a.reason)}</p>
                <p className="mono mt-1 text-[10px] text-[var(--text-muted)]">
                  {(a.memory_ids as string[]).join(" · ")}
                </p>
              </div>
            ))}
          </CardBody>
        </Card>
      ) : plan.data && !plan.isFetching ? (
        <EmptyState title="No consolidation actions" hint="Memory layer looks clean for the current scan." icon={GitBranch} />
      ) : null}
    </div>
  );
}

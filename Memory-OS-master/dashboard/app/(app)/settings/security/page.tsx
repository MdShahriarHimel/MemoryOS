"use client";

import { useQuery } from "@tanstack/react-query";
import { Clock, Key, RefreshCw, Shield, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { api, ApiError } from "@/lib/api/client";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { cn } from "@/lib/utils";

const RESULT_TONE: Record<string, "ok" | "warn" | "default"> = {
  ok: "ok",
  success: "ok",
  error: "warn",
  fail: "warn",
};

export default function SecuritySettingsPage() {
  const [actionFilter, setActionFilter] = useState("");
  const [appliedFilter, setAppliedFilter] = useState<string | undefined>(undefined);

  const logs = useQuery({
    queryKey: ["audit-logs", appliedFilter],
    queryFn: () => api.listAuditLogs({ limit: 100, action: appliedFilter }),
    refetchInterval: 30_000,
  });

  const forbidden = logs.error instanceof ApiError && logs.error.status === 403;

  return (
    <div className="mx-auto max-w-5xl animate-fade-in">
      <PageHeader
        title="Security"
        description="Append-only audit trail for API requests. Requires admin role (or owner in local anon mode)."
        action={
          <Button variant="secondary" size="sm" onClick={() => logs.refetch()} disabled={logs.isFetching}>
            <RefreshCw className={cn("h-3.5 w-3.5", logs.isFetching && "animate-spin")} />
            Refresh
          </Button>
        }
      />

      <div className="mb-6 grid gap-4 lg:grid-cols-3">
        <Card interactive glow="blue" className="lg:col-span-1">
          <CardHeader>
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <Key className="h-4 w-4 text-[var(--accent-blue)]" />
              Access control
            </h2>
          </CardHeader>
          <CardBody className="space-y-2 pt-0 text-xs text-[var(--text-secondary)]">
            <p>API keys use scoped bearer tokens. JWT users inherit role-based scopes.</p>
            <Link href="/api-keys">
              <Button variant="secondary" size="sm" className="mt-2 w-full">Manage API Keys</Button>
            </Link>
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardBody className="flex flex-wrap items-end gap-3">
            <div className="min-w-[200px] flex-1">
              <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
                Filter by action
              </label>
              <input
                value={actionFilter}
                onChange={(e) => setActionFilter(e.target.value)}
                placeholder="e.g. POST /v1/memory"
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm outline-none focus:border-[var(--accent-blue)]"
              />
            </div>
            <Button
              variant="secondary"
              onClick={() => setAppliedFilter(actionFilter.trim() || undefined)}
            >
              Apply filter
            </Button>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Shield className="h-4 w-4 text-[var(--accent-cyan)]" />
            Audit log
            {logs.data && <Badge tone="default">{logs.data.length} entries</Badge>}
          </h2>
        </CardHeader>
        <CardBody className="pt-0">
          {logs.isLoading ? (
            <LoadingState label="Loading audit logs" />
          ) : forbidden ? (
            <div className="py-8 text-center">
              <ShieldAlert className="mx-auto mb-3 h-8 w-8 text-[var(--warn)]" />
              <p className="text-sm text-[var(--text-secondary)]">Admin role required to view audit logs.</p>
              <Link href="/login" className="mt-3 inline-block text-xs text-[var(--accent-blue)] hover:underline">
                Sign in as admin
              </Link>
            </div>
          ) : logs.error ? (
            <ErrorState message="Could not load audit logs." onRetry={() => logs.refetch()} />
          ) : logs.data && logs.data.length > 0 ? (
            <ul className="max-h-[520px] space-y-2 overflow-y-auto">
              {logs.data.map((entry, i) => (
                <li
                  key={entry.id}
                  className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)]/30 p-3 opacity-0 animate-slide-up"
                  style={{ animationDelay: `${Math.min(i, 12) * 30}ms`, animationFillMode: "forwards" }}
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="mono text-xs font-medium text-[var(--text-primary)]">{entry.action}</p>
                      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-[var(--text-muted)]">
                        <span className="inline-flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {new Date(entry.at).toLocaleString()}
                        </span>
                        {entry.actor && <span>actor {entry.actor}</span>}
                        {entry.target && <span>target {entry.target}</span>}
                      </div>
                    </div>
                    <Badge tone={RESULT_TONE[entry.result.toLowerCase()] ?? "default"}>{entry.result}</Badge>
                  </div>
                  {entry.request_id && (
                    <p className="mono mt-2 text-[10px] text-[var(--text-muted)]">req {entry.request_id}</p>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              title="No audit entries yet"
              hint="Make API requests to populate the append-only audit trail."
              icon={Shield}
            />
          )}
        </CardBody>
      </Card>
    </div>
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";
import { Clock, Play, Users } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { api } from "@/lib/api/client";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { cn } from "@/lib/utils";

export default function SessionsPage() {
  const sessions = useQuery({
    queryKey: ["sessions"],
    queryFn: () => api.listSessions({ limit: 50 }),
  });

  const activeCount = sessions.data?.items.filter((s) => s.status === "active").length ?? 0;

  return (
    <div className="mx-auto max-w-4xl animate-fade-in">
      <PageHeader
        title="Sessions"
        description="Browse agent sessions and replay memory operations, retrievals, and context builds."
        action={
          sessions.data && (
            <Badge tone="cyan">
              {activeCount} active · {sessions.data.total} total
            </Badge>
          )
        }
      />

      {sessions.isLoading ? (
        <LoadingState label="Loading sessions" />
      ) : sessions.error ? (
        <ErrorState message="Could not load sessions." onRetry={() => sessions.refetch()} />
      ) : sessions.data && sessions.data.items.length > 0 ? (
        <ul className="space-y-3">
          {sessions.data.items.map((s, i) => (
            <li
              key={s.id}
              className="opacity-0 animate-slide-up"
              style={{ animationDelay: `${i * 50}ms`, animationFillMode: "forwards" }}
            >
              <Card interactive glow="blue" className="p-4">
                <div className="flex items-center gap-4">
                  <div className={cn(
                    "rounded-lg border p-2.5",
                    s.status === "active"
                      ? "border-[var(--accent-blue)]/30 bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]"
                      : "border-[var(--border)] text-[var(--text-muted)]",
                  )}>
                    <Users className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="mono truncate text-sm font-medium">{s.id}</p>
                      <Badge tone={s.status === "active" ? "ok" : "default"}>{s.status}</Badge>
                      {s.event_count > 0 && (
                        <Badge tone="purple">{s.event_count} events</Badge>
                      )}
                    </div>
                    <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-[var(--text-muted)]">
                      <span className="inline-flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {new Date(s.started_at).toLocaleString()}
                      </span>
                      {s.agent_id && <span>Agent {s.agent_id}</span>}
                    </p>
                  </div>
                  <Link href={s.event_count > 0 ? `/replay?session=${s.id}` : "#"} aria-disabled={s.event_count === 0}>
                    <Button variant="secondary" size="sm" disabled={s.event_count === 0} tabIndex={s.event_count === 0 ? -1 : 0}>
                      <Play className="h-3.5 w-3.5" />
                      Replay
                    </Button>
                  </Link>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState
          title="No sessions yet"
          hint="Create a session via POST /v1/sessions, then pass session_id on memory search or create calls."
          icon={Users}
        />
      )}
    </div>
  );
}

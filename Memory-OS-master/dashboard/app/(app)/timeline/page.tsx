"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Clock, GitCommit, Search } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { cn } from "@/lib/utils";

function TimelineContent() {
  const params = useSearchParams();
  const initialId = params.get("id") ?? "";
  const [memoryId, setMemoryId] = useState(initialId);
  const [inputId, setInputId] = useState(initialId);

  useEffect(() => {
    if (initialId) setMemoryId(initialId);
  }, [initialId]);

  const timeline = useQuery({
    queryKey: ["timeline", memoryId],
    queryFn: () => api.getTimeline(memoryId),
    enabled: !!memoryId,
  });

  return (
    <div className="mx-auto max-w-3xl animate-fade-in">
      <PageHeader
        title="Memory Timeline"
        description="Supersession chains, validity periods, and current truth resolution."
      />

      <Card className="p-4">
        <div className="flex gap-2">
          <input
            value={inputId}
            onChange={(e) => setInputId(e.target.value)}
            placeholder="Paste memory ID…"
            className="mono flex-1 rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm outline-none focus:border-[var(--accent-blue)]"
          />
          <Button variant="secondary" onClick={() => setMemoryId(inputId.trim())}>
            <Search className="h-4 w-4" />
            Load
          </Button>
        </div>
      </Card>

      <div className="mt-6">
        {!memoryId && (
          <EmptyState title="Enter a memory ID" hint="Open a memory in Explorer and click View timeline." icon={Clock} />
        )}
        {memoryId && timeline.isLoading && <LoadingState label="Loading timeline" />}
        {memoryId && timeline.error && (
          <ErrorState message="Could not load timeline." onRetry={() => timeline.refetch()} />
        )}
        {timeline.data && (
          <div className="space-y-6 animate-slide-up">
            {timeline.data.current_truth && (
              <Card className="border-[var(--accent-cyan)]/30 bg-[var(--accent-cyan)]/5 p-4">
                <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)]">Current truth</p>
                <p className="mt-1 text-lg font-semibold text-[var(--accent-cyan)]">
                  {String(timeline.data.current_truth.current_value)}
                </p>
              </Card>
            )}

            <div className="relative pl-6">
              <div className="absolute bottom-0 left-[11px] top-0 w-px bg-gradient-to-b from-[var(--accent-blue)] via-[var(--accent-purple)] to-transparent" />
              {timeline.data.chain.map((entry, i) => (
                <div
                  key={entry.memory_id}
                  className={cn(
                    "relative mb-6 opacity-0 animate-slide-up",
                  )}
                  style={{ animationDelay: `${i * 80}ms`, animationFillMode: "forwards" }}
                >
                  <div
                    className={cn(
                      "absolute -left-6 flex h-6 w-6 items-center justify-center rounded-full border-2 bg-[var(--bg)]",
                      entry.is_current
                        ? "border-[var(--accent-cyan)] shadow-[0_0_12px_rgba(34,211,238,0.4)]"
                        : "border-[var(--border)]",
                    )}
                  >
                    <GitCommit className="h-3 w-3 text-[var(--text-muted)]" />
                  </div>
                  <Card className={cn("p-4", entry.is_current && "border-[var(--accent-cyan)]/40")}>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={entry.is_current ? "cyan" : "default"}>
                        {entry.is_current ? "current" : entry.status.toLowerCase()}
                      </Badge>
                      <Badge tone="purple">v{entry.version}</Badge>
                    </div>
                    <p className="mt-2 text-sm text-[var(--text-primary)]">{entry.content}</p>
                    <p className="mono mt-2 text-[10px] text-[var(--text-muted)]">{entry.memory_id}</p>
                  </Card>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function TimelinePage() {
  return (
    <Suspense fallback={<LoadingState label="Loading" />}>
      <TimelineContent />
    </Suspense>
  );
}

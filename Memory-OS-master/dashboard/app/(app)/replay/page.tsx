"use client";

import { useQuery } from "@tanstack/react-query";
import { Pause, Play, SkipBack, Users } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { api } from "@/lib/api/client";
import type { SessionReplayEvent } from "@/lib/api/types";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { cn } from "@/lib/utils";

const TYPE_COLOR: Record<string, string> = {
  request: "#3b82f6", search: "#22d3ee", context: "#8b5cf6",
  response: "#34d399", memory_write: "#fbbf24",
};

function ReplayContent() {
  const params = useSearchParams();
  const sessionId = params.get("session") ?? "";
  const [playhead, setPlayhead] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const raf = useRef<number>(0);
  const last = useRef<number>(0);

  const replay = useQuery({
    queryKey: ["session-replay", sessionId],
    queryFn: () => api.getSessionEvents(sessionId),
    enabled: !!sessionId,
  });

  const events: SessionReplayEvent[] = useMemo(
    () => replay.data?.events ?? [],
    [replay.data?.events],
  );
  const total = events.length ? events[events.length - 1].t : 0;

  useEffect(() => {
    setPlaying(false);
    setPlayhead(0);
  }, [sessionId]);

  useEffect(() => {
    if (events.length > 0) {
      setPlayhead(events[events.length - 1].t);
    }
  }, [replay.data?.session_id, events.length, events]);

  useEffect(() => {
    if (!playing || total <= 0) return;
    last.current = performance.now();
    const tick = (now: number) => {
      const dt = ((now - last.current) / 1000) * speed;
      last.current = now;
      setPlayhead((p) => {
        const next = p + dt;
        if (next >= total) { setPlaying(false); return total; }
        return next;
      });
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [playing, speed, total]);

  const active = events.filter((e) => e.t <= playhead);
  const progress = total > 0 ? (playhead / total) * 100 : 0;

  return (
    <div className="mx-auto max-w-4xl animate-fade-in">
      <PageHeader
        title="Session Replay"
        description="Scrub through a session's memory operations, retrievals, and context builds."
        action={
          sessionId ? (
            <Badge tone="cyan" className="mono max-w-[200px] truncate">{sessionId}</Badge>
          ) : undefined
        }
      />

      {!sessionId ? (
        <Card glow="purple" className="overflow-hidden">
          <CardBody>
            <EmptyState
              title="No session loaded"
              hint="Open a session from the Sessions page to replay its event timeline."
              icon={Play}
            />
            <div className="flex justify-center pb-8">
              <Link href="/sessions">
                <Button variant="secondary">
                  <Users className="h-4 w-4" />
                  Go to Sessions
                </Button>
              </Link>
            </div>
          </CardBody>
        </Card>
      ) : replay.isLoading ? (
        <LoadingState label="Loading replay" />
      ) : replay.error ? (
        <ErrorState message="Could not load session events." onRetry={() => replay.refetch()} />
      ) : events.length === 0 ? (
        <Card glow="purple" className="overflow-hidden">
          <CardBody>
            <EmptyState
              title="No events recorded"
              hint="This session has no events yet. Pass session_id on search, context, or memory create calls."
              icon={Play}
            />
            <div className="flex justify-center pb-8">
              <Link href="/sessions">
                <Button variant="secondary">Back to Sessions</Button>
              </Link>
            </div>
          </CardBody>
        </Card>
      ) : (
        <>
          <Card className="mb-6 overflow-hidden">
            <div className="border-b border-[var(--border)] bg-gradient-to-r from-[var(--accent-blue)]/10 to-[var(--accent-purple)]/5 px-5 py-4">
              <div className="mb-3 h-1.5 overflow-hidden rounded-full bg-[var(--surface-2)]">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-[var(--accent-blue)] to-[var(--accent-purple)] transition-all duration-75"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="flex items-center gap-3">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => { setPlayhead(0); setPlaying(false); }}
                  aria-label="Restart"
                >
                  <SkipBack className="h-4 w-4" />
                </Button>
                <Button
                  size="sm"
                  onClick={() => setPlaying((p) => !p)}
                  aria-label={playing ? "Pause" : "Play"}
                >
                  {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                </Button>
                <input
                  type="range"
                  min={0}
                  max={total}
                  step={0.01}
                  value={playhead}
                  onChange={(e) => setPlayhead(Number(e.target.value))}
                  className="flex-1 accent-[var(--accent-blue)]"
                  aria-label="Timeline scrubber"
                />
                <span className="mono w-14 text-right text-xs text-[var(--text-muted)]">
                  {playhead.toFixed(1)}s
                </span>
                <select
                  value={speed}
                  onChange={(e) => setSpeed(Number(e.target.value))}
                  className="rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-xs outline-none focus:border-[var(--accent-blue)]"
                  aria-label="Speed"
                >
                  {[0.5, 1, 2, 4].map((s) => <option key={s} value={s}>{s}×</option>)}
                </select>
              </div>
            </div>
          </Card>

          <ol className="space-y-3">
            {active.map((e, i) => (
              <li
                key={e.seq}
                className="opacity-0 animate-slide-up"
                style={{ animationDelay: `${i * 40}ms`, animationFillMode: "forwards" }}
              >
                <Card
                  interactive
                  className={cn(
                    "p-4",
                    e.t <= playhead && e.t >= playhead - 0.5 && "border-[var(--accent-blue)]/40",
                  )}
                >
                  <div className="flex items-start gap-3">
                    <span className="mono w-12 shrink-0 text-xs text-[var(--text-muted)]">{e.t.toFixed(2)}s</span>
                    <span
                      className="mt-1.5 h-2 w-2 shrink-0 rounded-full shadow-sm"
                      style={{
                        background: TYPE_COLOR[e.type] ?? "#94a3b8",
                        boxShadow: `0 0 8px ${TYPE_COLOR[e.type] ?? "#94a3b8"}66`,
                      }}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium capitalize">{e.type.replace("_", " ")}</p>
                      <p className="text-xs text-[var(--text-muted)]">{e.detail}</p>
                    </div>
                    {e.latency_ms != null && (
                      <Badge tone="cyan">{e.latency_ms}ms</Badge>
                    )}
                  </div>
                </Card>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}

export default function ReplayPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading replay" />}>
      <ReplayContent />
    </Suspense>
  );
}

"use client";

import { AlertTriangle, Inbox, Loader2, WifiOff } from "lucide-react";
import { cn } from "@/lib/utils";

// Honest state components. The product rule: never render fake data as a
// fallback. When the backend has nothing (or is unreachable), we say so.

export function LoadingState({ label = "Loading", className }: { label?: string; className?: string }) {
  return (
    <div className={cn("flex items-center gap-2 text-sm text-[var(--text-muted)] py-10 justify-center", className)}>
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      <span>{label}…</span>
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-[var(--surface-2)]", className)}
      aria-hidden
    />
  );
}

export function EmptyState({
  title,
  hint,
  icon: Icon = Inbox,
}: {
  title: string;
  hint?: string;
  icon?: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-3 rounded-full border border-[var(--border)] p-3 text-[var(--text-muted)]">
        <Icon className="h-5 w-5" />
      </div>
      <p className="text-sm font-medium text-[var(--text-secondary)]">{title}</p>
      {hint ? <p className="mt-1 text-xs text-[var(--text-muted)]">{hint}</p> : null}
    </div>
  );
}

export function ErrorState({
  message,
  requestId,
  onRetry,
}: {
  message: string;
  requestId?: string | null;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-3 rounded-full border border-[var(--err)]/30 bg-[var(--err)]/10 p-3 text-[var(--err)]">
        <AlertTriangle className="h-5 w-5" />
      </div>
      <p className="text-sm font-medium text-[var(--text-secondary)]">{message}</p>
      {requestId ? (
        <p className="mono mt-1 text-xs text-[var(--text-muted)]">request_id: {requestId}</p>
      ) : null}
      {onRetry ? (
        <button
          onClick={onRetry}
          className="mt-4 rounded-md border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]"
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function UnavailableState({ onRetry }: { onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-3 rounded-full border border-[var(--warn)]/30 bg-[var(--warn)]/10 p-3 text-[var(--warn)]">
        <WifiOff className="h-5 w-5" />
      </div>
      <p className="text-sm font-medium text-[var(--text-secondary)]">
        MEMORY OS API is unavailable
      </p>
      <p className="mt-1 text-xs text-[var(--text-muted)]">
        Check that the API service is running and reachable.
      </p>
      {onRetry ? (
        <button
          onClick={onRetry}
          className="mt-4 rounded-md border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:border-[var(--border-strong)]"
        >
          Retry connection
        </button>
      ) : null}
    </div>
  );
}

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Plus, Shield, Trash2, Webhook } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { api } from "@/lib/api/client";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { cn } from "@/lib/utils";

const EVENTS = [
  "memory.created", "memory.updated", "memory.deleted", "memory.conflict",
  "session.started", "session.completed", "reflection.completed",
];

const EVENT_TONE: Record<string, "blue" | "cyan" | "purple" | "warn" | "ok" | "default"> = {
  "memory.created": "ok",
  "memory.updated": "blue",
  "memory.deleted": "warn",
  "memory.conflict": "warn",
  "session.started": "cyan",
  "session.completed": "purple",
  "reflection.completed": "purple",
};

export default function WebhooksPage() {
  const qc = useQueryClient();
  const hooks = useQuery({ queryKey: ["webhooks"], queryFn: api.listWebhooks });
  const [url, setUrl] = useState("");
  const [events, setEvents] = useState<string[]>(["memory.created"]);
  const [secret, setSecret] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const create = useMutation({
    mutationFn: () => api.createWebhook({ url, events }),
    onSuccess: (res) => {
      setSecret(res.secret);
      setUrl("");
      qc.invalidateQueries({ queryKey: ["webhooks"] });
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.deleteWebhook(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["webhooks"] }),
  });

  async function copySecret() {
    if (!secret) return;
    await navigator.clipboard.writeText(secret);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const activeCount = hooks.data?.length ?? 0;

  return (
    <div className="mx-auto max-w-4xl animate-fade-in">
      <PageHeader
        title="Webhooks"
        description="Receive signed memory and session events. Payloads include an HMAC X-MemoryOS-Signature header."
        action={
          hooks.data && (
            <Badge tone="cyan">{activeCount} endpoint{activeCount !== 1 ? "s" : ""}</Badge>
          )
        }
      />

      {secret && (
        <Card className="mb-6 border-[var(--accent-cyan)]/40 bg-gradient-to-r from-[var(--accent-cyan)]/10 to-[var(--accent-blue)]/5 animate-scale-in">
          <CardBody>
            <div className="flex items-start gap-3">
              <div className="rounded-lg bg-[var(--accent-cyan)]/20 p-2 text-[var(--accent-cyan)]">
                <Shield className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-[var(--text-primary)]">Copy your signing secret now</p>
                <p className="text-xs text-[var(--text-muted)]">Used to verify webhook payloads. Shown once.</p>
                <div className="mono mt-3 flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-xs">
                  <span className="truncate">{secret}</span>
                  <Button variant="ghost" size="sm" onClick={copySecret} className="ml-auto shrink-0">
                    {copied ? <Check className="h-3.5 w-3.5 text-[var(--ok)]" /> : <Copy className="h-3.5 w-3.5" />}
                  </Button>
                </div>
              </div>
            </div>
          </CardBody>
        </Card>
      )}

      <Card className="mb-8 overflow-hidden">
        <div className="border-b border-[var(--border)] bg-gradient-to-r from-[var(--accent-cyan)]/5 to-transparent px-5 py-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Plus className="h-4 w-4 text-[var(--accent-cyan)]" />
            Add endpoint
          </h2>
        </div>
        <CardBody className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">Endpoint URL</label>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://your-app.com/webhooks/memory-os"
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-sm outline-none transition-colors focus:border-[var(--accent-cyan)] focus:ring-1 focus:ring-[var(--accent-cyan)]/30"
            />
          </div>
          <div>
            <label className="mb-2 block text-xs font-medium text-[var(--text-secondary)]">Events</label>
            <div className="flex flex-wrap gap-2">
              {EVENTS.map((ev) => {
                const on = events.includes(ev);
                return (
                  <button
                    key={ev}
                    type="button"
                    onClick={() => setEvents((c) => (on ? c.filter((x) => x !== ev) : [...c, ev]))}
                    className={cn(
                      "mono rounded-lg border px-2.5 py-1.5 text-[11px] font-medium transition-all duration-200",
                      on
                        ? "border-[var(--accent-cyan)] bg-[var(--accent-cyan)]/15 text-[var(--text-primary)] shadow-sm"
                        : "border-[var(--border)] text-[var(--text-muted)] hover:border-[var(--border-strong)] hover:bg-[var(--surface-2)]",
                    )}
                  >
                    {ev}
                  </button>
                );
              })}
            </div>
          </div>
          <Button onClick={() => create.mutate()} disabled={!url} loading={create.isPending}>
            <Webhook className="h-4 w-4" />
            Add endpoint
          </Button>
        </CardBody>
      </Card>

      <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--text-muted)]">Your endpoints</h2>

      {hooks.isLoading ? (
        <LoadingState label="Loading webhooks" />
      ) : hooks.error ? (
        <ErrorState message="Could not load webhooks." onRetry={() => hooks.refetch()} />
      ) : hooks.data && hooks.data.length > 0 ? (
        <ul className="space-y-3">
          {hooks.data.map((h, i) => (
            <li
              key={h.id}
              className="opacity-0 animate-slide-up"
              style={{ animationDelay: `${i * 50}ms`, animationFillMode: "forwards" }}
            >
              <Card interactive glow="cyan" className="p-4">
                <div className="flex items-center gap-4">
                  <div className="rounded-lg border border-[var(--accent-cyan)]/30 bg-[var(--accent-cyan)]/10 p-2.5 text-[var(--accent-cyan)]">
                    <Webhook className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="truncate text-sm font-medium">{h.url}</p>
                      <Badge tone={h.status === "active" ? "ok" : "default"}>{h.status}</Badge>
                    </div>
                    <p className="mono mt-1 text-[11px] text-[var(--text-muted)]">
                      Created {new Date(h.created_at).toLocaleDateString()}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {(h.events.length ? h.events : ["all events"]).map((ev) => (
                        <Badge key={ev} tone={EVENT_TONE[ev] ?? "default"}>{ev}</Badge>
                      ))}
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => remove.mutate(h.id)}
                    disabled={remove.isPending}
                    aria-label="Delete webhook"
                    className="text-[var(--text-muted)] hover:text-[var(--err)]"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState title="No webhook endpoints" hint="Add one to receive memory and session events." icon={Webhook} />
      )}
    </div>
  );
}

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, KeyRound, Plus, Shield, Trash2 } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { api, ApiError, ConnectionError } from "@/lib/api/client";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { cn } from "@/lib/utils";

const SCOPES = ["memory:read", "memory:write", "graph:read", "sessions:read", "analytics:read", "admin"];

const SCOPE_TONE: Record<string, "blue" | "purple" | "cyan" | "ok" | "warn" | "default"> = {
  "memory:read": "blue",
  "memory:write": "cyan",
  "graph:read": "purple",
  "sessions:read": "default",
  "analytics:read": "ok",
  admin: "warn",
};

export default function ApiKeysPage() {
  const qc = useQueryClient();
  const keys = useQuery({ queryKey: ["apikeys"], queryFn: api.listApiKeys });
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<string[]>(["memory:read"]);
  const [revealed, setRevealed] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const create = useMutation({
    mutationFn: () => api.createApiKey({ name: name.trim(), scopes: selected }),
    onSuccess: (res) => {
      setRevealed(res.secret);
      setName("");
      qc.invalidateQueries({ queryKey: ["apikeys"] });
    },
  });

  const createError =
    create.error instanceof ApiError
      ? create.error.message
      : create.error instanceof ConnectionError
        ? "Cannot reach the MEMORY OS API."
        : create.error
          ? "Could not create API key."
          : null;

  const revoke = useMutation({
    mutationFn: (id: string) => api.revokeApiKey(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["apikeys"] }),
  });

  async function copySecret() {
    if (!revealed) return;
    await navigator.clipboard.writeText(revealed);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const activeCount = keys.data?.filter((k) => !k.revoked).length ?? 0;

  return (
    <div className="mx-auto max-w-4xl animate-fade-in">
      <PageHeader
        title="API Keys"
        description="Authenticate external agents and SDKs to MEMORY OS. These are not LLM or embedding provider keys."
        action={
          keys.data && (
            <Badge tone="cyan">{activeCount} active key{activeCount !== 1 ? "s" : ""}</Badge>
          )
        }
      />

      {revealed && (
        <Card className="mb-6 border-[var(--accent-blue)]/40 bg-gradient-to-r from-[var(--accent-blue)]/10 to-[var(--accent-purple)]/5 animate-scale-in">
          <CardBody>
            <div className="flex items-start gap-3">
              <div className="rounded-lg bg-[var(--accent-blue)]/20 p-2 text-[var(--accent-blue)]">
                <Shield className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-[var(--text-primary)]">Copy your secret now</p>
                <p className="text-xs text-[var(--text-muted)]">It will not be shown again after you leave this page.</p>
                <div className="mono mt-3 flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-xs">
                  <span className="truncate">{revealed}</span>
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
        <div className="border-b border-[var(--border)] bg-gradient-to-r from-[var(--accent-purple)]/5 to-transparent px-5 py-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Plus className="h-4 w-4 text-[var(--accent-purple)]" />
            Create new key
          </h2>
        </div>
        <CardBody className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">Key name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. production-agent"
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-sm outline-none transition-colors focus:border-[var(--accent-blue)] focus:ring-1 focus:ring-[var(--accent-blue)]/30"
            />
          </div>
          <div>
            <label className="mb-2 block text-xs font-medium text-[var(--text-secondary)]">Scopes</label>
            <div className="flex flex-wrap gap-2">
              {SCOPES.map((s) => {
                const on = selected.includes(s);
                return (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setSelected((cur) => (on ? cur.filter((x) => x !== s) : [...cur, s]))}
                    className={cn(
                      "mono rounded-lg border px-2.5 py-1.5 text-[11px] font-medium transition-all duration-200",
                      on
                        ? "border-[var(--accent-purple)] bg-[var(--accent-purple)]/15 text-[var(--text-primary)] shadow-sm"
                        : "border-[var(--border)] text-[var(--text-muted)] hover:border-[var(--border-strong)] hover:bg-[var(--surface-2)]",
                    )}
                  >
                    {s}
                  </button>
                );
              })}
            </div>
          </div>
          <Button onClick={() => create.mutate()} disabled={!name.trim()} loading={create.isPending}>
            <KeyRound className="h-4 w-4" />
            Create key
          </Button>
          {createError && (
            <p className="rounded-lg border border-[var(--err)]/30 bg-[var(--err)]/10 px-3 py-2 text-xs text-[var(--err)]">
              {createError}
            </p>
          )}
        </CardBody>
      </Card>

      <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--text-muted)]">Your keys</h2>

      {keys.isLoading ? (
        <LoadingState label="Loading keys" />
      ) : keys.error ? (
        <ErrorState message="Could not load API keys." onRetry={() => keys.refetch()} />
      ) : keys.data && keys.data.length > 0 ? (
        <ul className="space-y-3">
          {keys.data.map((k, i) => (
            <li
              key={k.id}
              className="opacity-0 animate-slide-up"
              style={{ animationDelay: `${i * 50}ms`, animationFillMode: "forwards" }}
            >
              <Card
                interactive
                className={cn("p-4", k.revoked && "opacity-60")}
              >
                <div className="flex items-center gap-4">
                  <div className={cn(
                    "rounded-lg border p-2.5",
                    k.revoked
                      ? "border-[var(--border)] text-[var(--text-muted)]"
                      : "border-[var(--accent-blue)]/30 bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]",
                  )}>
                    <KeyRound className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="truncate text-sm font-medium">{k.name}</p>
                      {k.revoked ? (
                        <Badge tone="warn">revoked</Badge>
                      ) : (
                        <Badge tone="ok">active</Badge>
                      )}
                    </div>
                    <p className="mono mt-1 text-[11px] text-[var(--text-muted)]">
                      {k.prefix}··· · {k.environment} · last used {k.last_used_at ? new Date(k.last_used_at).toLocaleDateString() : "never"}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {k.scopes.map((s) => (
                        <Badge key={s} tone={SCOPE_TONE[s] ?? "default"}>{s}</Badge>
                      ))}
                    </div>
                  </div>
                  {!k.revoked && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => revoke.mutate(k.id)}
                      disabled={revoke.isPending}
                      aria-label="Revoke key"
                      className="text-[var(--text-muted)] hover:text-[var(--err)]"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </Card>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState title="No API keys yet" hint="Create one to connect an external agent or SDK." icon={KeyRound} />
      )}
    </div>
  );
}

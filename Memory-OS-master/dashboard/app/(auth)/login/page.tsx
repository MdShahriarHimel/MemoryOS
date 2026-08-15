"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Brain, Lock, Sparkles, Zap } from "lucide-react";
import { api, ApiError, ConnectionError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const FEATURES = [
  { icon: Brain, title: "Deterministic memory", desc: "No LLM inside — your models stay external." },
  { icon: Sparkles, title: "Hybrid retrieval", desc: "Vector, keyword, graph, and temporal fusion." },
  { icon: Lock, title: "Tenant isolated", desc: "RLS-hardened PostgreSQL with audit trails." },
];

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [org, setOrg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "login") {
        await api.login({ email, password });
      } else {
        await api.register({ email, password, organization_name: org });
      }
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof ConnectionError) setError("Cannot reach the MEMORY OS API.");
      else if (err instanceof ApiError) setError(err.message);
      else setError("Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-screen overflow-hidden">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -left-32 top-0 h-96 w-96 rounded-full bg-[var(--accent-blue)]/20 blur-[100px] animate-pulse-glow" />
        <div className="absolute -right-32 bottom-0 h-96 w-96 rounded-full bg-[var(--accent-purple)]/15 blur-[100px] animate-pulse-glow" style={{ animationDelay: "1s" }} />
      </div>

      <div className="relative hidden w-1/2 flex-col justify-between border-r border-[var(--border)] p-12 lg:flex">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-[var(--accent-blue)] to-[var(--accent-purple)] shadow-lg shadow-blue-500/30" />
          <div>
            <span className="font-display text-xl font-bold">MEMORY OS</span>
            <p className="text-[10px] uppercase tracking-widest text-[var(--text-muted)]">Cognitive infrastructure</p>
          </div>
        </div>
        <div className="space-y-8">
          <h2 className="font-display text-4xl font-semibold leading-tight tracking-tight">
            Durable memory for{" "}
            <span className="gradient-text">AI agents</span>
          </h2>
          <ul className="space-y-4">
            {FEATURES.map((f) => {
              const Icon = f.icon;
              return (
                <li key={f.title} className="flex gap-4">
                  <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-1)]/80 p-2.5 text-[var(--accent-cyan)]">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="font-medium text-[var(--text-primary)]">{f.title}</p>
                    <p className="text-sm text-[var(--text-muted)]">{f.desc}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
        <p className="text-xs text-[var(--text-muted)]">v0.3 · Model-independent · Zero fake data</p>
      </div>

      <div className="relative flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-md animate-slide-up">
          <div className="mb-8 flex items-center gap-2 lg:hidden">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-[var(--accent-blue)] to-[var(--accent-purple)]" />
            <span className="font-display text-lg font-bold">MEMORY OS</span>
          </div>

          <Card className="gradient-border p-6 shadow-2xl shadow-black/20">
            <div className="mb-6 flex gap-1 rounded-lg border border-[var(--border)] bg-[var(--bg)] p-1">
              {(["login", "register"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  className={`flex-1 rounded-md px-3 py-2 text-sm font-medium capitalize transition-all duration-200 ${
                    mode === m
                      ? "bg-[var(--surface-2)] text-[var(--text-primary)] shadow-sm"
                      : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>

            <form onSubmit={submit} className="space-y-4">
              {mode === "register" && (
                <Field label="Organization" value={org} onChange={setOrg} placeholder="Acme Inc." />
              )}
              <Field label="Email" type="email" value={email} onChange={setEmail} placeholder="you@company.com" />
              <Field label="Password" type="password" value={password} onChange={setPassword} placeholder="••••••••" />
              {error && (
                <p className="rounded-lg border border-[var(--err)]/30 bg-[var(--err)]/10 px-3 py-2 text-xs text-[var(--err)]">
                  {error}
                </p>
              )}
              <Button type="submit" className="w-full" loading={busy}>
                <Zap className="h-4 w-4" />
                {mode === "login" ? "Sign in" : "Create account"}
              </Button>
            </form>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Field({
  label, value, onChange, type = "text", placeholder,
}: {
  label: string; value: string; onChange: (v: string) => void; type?: string; placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required
        className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-sm outline-none transition-colors focus:border-[var(--accent-blue)] focus:ring-1 focus:ring-[var(--accent-blue)]/30"
      />
    </label>
  );
}

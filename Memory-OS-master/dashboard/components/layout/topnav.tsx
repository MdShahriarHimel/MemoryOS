"use client";

import { Bell, Command, LogOut, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import type { ReadyState } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const DOT: Record<string, string> = {
  operational: "var(--ok)",
  degraded: "var(--warn)",
  unavailable: "var(--err)",
};

const QUICK_LINKS = [
  { label: "Memory Explorer", href: "/memory-explorer" },
  { label: "Context Builder", href: "/context-builder" },
  { label: "Knowledge Graph", href: "/knowledge-graph" },
  { label: "Analytics", href: "/analytics" },
  { label: "API Keys", href: "/api-keys" },
];

export function TopNav() {
  const router = useRouter();
  const [health, setHealth] = useState<ReadyState | null>(null);
  const [failed, setFailed] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let alive = true;
    api.getReady().then((r) => alive && setHealth(r)).catch(() => alive && setFailed(true));
    return () => { alive = false; };
  }, []);

  const togglePalette = useCallback(() => setPaletteOpen((o) => !o), []);

  async function signOut() {
    await api.logout();
    router.push("/login");
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        togglePalette();
      }
      if (e.key === "Escape") setPaletteOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [togglePalette]);

  const status = failed ? "unavailable" : health?.status ?? "loading";
  const filtered = QUICK_LINKS.filter((l) =>
    l.label.toLowerCase().includes(query.toLowerCase()),
  );

  return (
    <>
      <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-[var(--border)] glass-strong px-4 md:px-6">
        <button
          type="button"
          onClick={togglePalette}
          className="group flex flex-1 max-w-md items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-1)]/80 px-3 py-2 text-xs text-[var(--text-muted)] transition-all hover:border-[var(--border-strong)] hover:bg-[var(--surface-2)]"
          aria-label="Command palette"
        >
          <Search className="h-3.5 w-3.5 transition-colors group-hover:text-[var(--accent-blue)]" />
          <span className="hidden sm:inline">Search pages, memories…</span>
          <span className="sm:hidden">Search…</span>
          <kbd className="mono ml-auto hidden rounded border border-[var(--border)] bg-[var(--bg)] px-1.5 py-0.5 text-[10px] sm:inline">
            ⌘K
          </kbd>
        </button>

        <div className="ml-auto flex items-center gap-2 md:gap-3">
          <div className="hidden sm:flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-1)]/80 px-2.5 py-1.5 text-xs text-[var(--text-muted)]">
            <span className="h-2 w-2 rounded-full bg-[var(--accent-cyan)]" />
            Connected
          </div>

          <div className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-1)]/80 px-2.5 py-1.5 text-xs">
            <span
              className={cn(
                "relative h-2 w-2 rounded-full",
                status === "operational" && "animate-pulse-glow",
              )}
              style={{ background: DOT[status] ?? "var(--text-muted)" }}
            />
            <span className="hidden text-[var(--text-secondary)] capitalize sm:inline">
              {status === "loading" ? "Checking…" : status}
            </span>
          </div>

          <button
            type="button"
            className="rounded-lg p-2 text-[var(--text-muted)] transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]"
            aria-label="Notifications"
          >
            <Bell className="h-4 w-4" />
          </button>

          <button
            type="button"
            onClick={() => void signOut()}
            className="rounded-lg p-2 text-[var(--text-muted)] transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]"
            aria-label="Sign out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </header>

      {paletteOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] px-4">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setPaletteOpen(false)} />
          <div className="relative w-full max-w-lg overflow-hidden rounded-xl border border-[var(--border-strong)] bg-[var(--surface-1)] shadow-2xl animate-scale-in">
            <div className="flex items-center gap-2 border-b border-[var(--border)] px-4 py-3">
              <Command className="h-4 w-4 text-[var(--accent-blue)]" />
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Jump to page…"
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-[var(--text-muted)]"
              />
              <kbd className="mono rounded border border-[var(--border)] px-1.5 py-0.5 text-[10px] text-[var(--text-muted)]">esc</kbd>
            </div>
            <ul className="max-h-64 overflow-y-auto p-2">
              {filtered.map((link) => (
                <li key={link.href}>
                  <button
                    type="button"
                    onClick={() => { router.push(link.href); setPaletteOpen(false); }}
                    className="w-full rounded-lg px-3 py-2.5 text-left text-sm text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]"
                  >
                    {link.label}
                  </button>
                </li>
              ))}
              {filtered.length === 0 && (
                <li className="px-3 py-6 text-center text-sm text-[var(--text-muted)]">No matches</li>
              )}
            </ul>
          </div>
        </div>
      )}
    </>
  );
}

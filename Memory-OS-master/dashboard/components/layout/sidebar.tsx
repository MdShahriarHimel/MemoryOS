"use client";

import {
  Activity, Clock, Database, FlaskConical, GitBranch, Key, LayoutDashboard,
  Menu, Network, Play, Puzzle, ScrollText, Search, Settings, Shield, Sparkles, Terminal,
  Users, Webhook, X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

type Item = { label: string; href: string; icon: React.ComponentType<{ className?: string }> };
type Group = { title: string; items: Item[] };

const GROUPS: Group[] = [
  { title: "Overview", items: [{ label: "Dashboard", href: "/dashboard", icon: LayoutDashboard }] },
  {
    title: "Memory",
    items: [
      { label: "Memory Explorer", href: "/memory-explorer", icon: Search },
      { label: "Timeline", href: "/timeline", icon: Clock },
      { label: "Knowledge Graph", href: "/knowledge-graph", icon: Network },
    ],
  },
  {
    title: "Cognition",
    items: [
      { label: "Context Builder", href: "/context-builder", icon: Sparkles },
      { label: "Reflection", href: "/reflection", icon: GitBranch },
    ],
  },
  {
    title: "Agents",
    items: [
      { label: "Sessions", href: "/sessions", icon: Users },
      { label: "Replay", href: "/replay", icon: Play },
    ],
  },
  {
    title: "Observability",
    items: [
      { label: "Analytics", href: "/analytics", icon: Activity },
      { label: "System Health", href: "/system-health", icon: Database },
      { label: "Audit Log", href: "/audit-log", icon: ScrollText },
      { label: "MemoryBench", href: "/benchmarks", icon: FlaskConical },
    ],
  },
  {
    title: "Developer",
    items: [
      { label: "Developer Portal", href: "/developer", icon: Terminal },
      { label: "API Keys", href: "/api-keys", icon: Key },
      { label: "Webhooks", href: "/webhooks", icon: Webhook },
      { label: "MCP", href: "/mcp", icon: Puzzle },
    ],
  },
  {
    title: "Settings",
    items: [
      { label: "Organization", href: "/settings/organization", icon: Settings },
      { label: "Security", href: "/settings/security", icon: Shield },
    ],
  },
];

function NavContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <div className="flex-1 overflow-y-auto py-4 px-3 space-y-6">
      {GROUPS.map((g, gi) => (
        <div key={g.title} className="animate-slide-in-left" style={{ animationDelay: `${gi * 40}ms` }}>
          <p className="px-3 mb-2 text-[10px] font-semibold uppercase tracking-widest text-[var(--text-muted)]">
            {g.title}
          </p>
          <ul className="space-y-0.5">
            {g.items.map((it) => {
              const active = pathname === it.href || pathname.startsWith(it.href + "/");
              const Icon = it.icon;
              return (
                <li key={it.href}>
                  <Link
                    href={it.href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-[13px] transition-all duration-200",
                      active
                        ? "bg-[var(--surface-2)] text-[var(--text-primary)] shadow-sm"
                        : "text-[var(--text-secondary)] hover:bg-[var(--surface-2)]/50 hover:text-[var(--text-primary)]",
                    )}
                  >
                    {active && <span className="nav-active-indicator" aria-hidden />}
                    <Icon
                      className={cn(
                        "h-4 w-4 shrink-0 transition-colors",
                        active ? "text-[var(--accent-cyan)]" : "text-[var(--text-muted)] group-hover:text-[var(--accent-blue)]",
                      )}
                    />
                    <span className="truncate font-medium">{it.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}

export function Sidebar() {
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMobileOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mobileOpen]);

  return (
    <>
      <button
        type="button"
        onClick={() => setMobileOpen(true)}
        className="fixed bottom-5 left-5 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-[var(--accent-blue)] to-[var(--accent-purple)] text-white shadow-lg shadow-blue-500/30 md:hidden"
        aria-label="Open menu"
      >
        <Menu className="h-5 w-5" />
      </button>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setMobileOpen(false)} />
          <nav className="absolute inset-y-0 left-0 flex w-72 flex-col border-r border-[var(--border)] bg-[var(--surface-1)] shadow-2xl animate-slide-in-left">
            <SidebarHeader onClose={() => setMobileOpen(false)} />
            <NavContent onNavigate={() => setMobileOpen(false)} />
          </nav>
        </div>
      )}

      <nav
        aria-label="Primary"
        className="hidden md:flex w-64 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--surface-1)]/40 glass h-screen sticky top-0"
      >
        <SidebarHeader />
        <NavContent />
        <div className="border-t border-[var(--border)] p-4">
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)]/50 p-3">
            <p className="text-[11px] font-medium text-[var(--text-secondary)]">MEMORY OS v0.3</p>
            <p className="mt-0.5 text-[10px] text-[var(--text-muted)]">Model-independent memory</p>
          </div>
        </div>
      </nav>
    </>
  );
}

function SidebarHeader({ onClose }: { onClose?: () => void }) {
  return (
    <div className="flex h-14 items-center justify-between gap-2 px-4 border-b border-[var(--border)]">
      <Link href="/dashboard" className="flex items-center gap-2.5 group">
        <div className="relative h-8 w-8 rounded-lg bg-gradient-to-br from-[var(--accent-blue)] to-[var(--accent-purple)] shadow-lg shadow-blue-500/25 transition-transform group-hover:scale-105">
          <div className="absolute inset-0 rounded-lg bg-gradient-to-br from-white/20 to-transparent" />
        </div>
        <div>
          <span className="font-display text-sm font-bold tracking-tight">MEMORY OS</span>
          <p className="text-[9px] uppercase tracking-widest text-[var(--text-muted)]">Cognitive Layer</p>
        </div>
      </Link>
      {onClose && (
        <button type="button" onClick={onClose} className="rounded-md p-1.5 text-[var(--text-muted)] hover:bg-[var(--surface-2)]" aria-label="Close menu">
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

export { Sidebar as default };

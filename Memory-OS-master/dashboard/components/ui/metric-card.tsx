"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { Card } from "./card";

function AnimatedValue({ value }: { value: string }) {
  const [display, setDisplay] = useState(value);
  useEffect(() => {
    setDisplay(value);
  }, [value]);
  return (
    <span className="metric text-2xl font-semibold text-[var(--text-primary)] transition-all duration-300">
      {display}
    </span>
  );
}

export function MetricCard({
  label,
  value,
  icon: Icon,
  tone = "blue",
  unavailable,
  delay = 0,
  trend,
}: {
  label: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  tone?: "blue" | "purple" | "cyan" | "ok";
  unavailable?: boolean;
  delay?: number;
  trend?: string;
}) {
  const iconColor = {
    blue: "text-[var(--accent-blue)]",
    purple: "text-[var(--accent-purple)]",
    cyan: "text-[var(--accent-cyan)]",
    ok: "text-[var(--ok)]",
  }[tone];

  const glowBg = {
    blue: "from-[var(--accent-blue)]/20 to-transparent",
    purple: "from-[var(--accent-purple)]/20 to-transparent",
    cyan: "from-[var(--accent-cyan)]/20 to-transparent",
    ok: "from-[var(--ok)]/20 to-transparent",
  }[tone];

  return (
    <Card
      interactive
      glow={tone === "ok" ? undefined : tone}
      className={cn(
        "relative overflow-hidden p-4 opacity-0 animate-slide-up",
        `stagger-${Math.min(delay + 1, 6)}`,
      )}
      style={{ animationDelay: `${delay * 60}ms`, animationFillMode: "forwards" }}
    >
      <div className={cn("pointer-events-none absolute -right-4 -top-4 h-24 w-24 rounded-full bg-gradient-to-br opacity-60 blur-2xl", glowBg)} />
      <div className="relative flex items-start justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">{label}</span>
        <div className={cn("rounded-lg border border-[var(--border)] bg-[var(--surface-2)]/80 p-2", iconColor)}>
          <Icon className="h-4 w-4" />
        </div>
      </div>
      <div className="relative mt-3">
        <AnimatedValue value={value} />
        {trend && <p className="mt-1 text-[11px] text-[var(--text-muted)]">{trend}</p>}
        {unavailable && (
          <p className="mt-1 text-[11px] text-[var(--warn)]">Requires analytics pipeline</p>
        )}
      </div>
    </Card>
  );
}

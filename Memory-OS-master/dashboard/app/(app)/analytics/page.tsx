"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, Database, Layers, TrendingUp } from "lucide-react";
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { MetricCard } from "@/components/ui/metric-card";
import { PageHeader } from "@/components/ui/page-header";
import { api } from "@/lib/api/client";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { formatNumber } from "@/lib/utils";

function ChartCard({
  kind, title, desc, color, icon: Icon, delay = 0,
}: {
  kind: string; title: string; desc: string; color: string;
  icon: React.ComponentType<{ className?: string }>; delay?: number;
}) {
  const q = useQuery({ queryKey: ["series", kind], queryFn: () => api.analyticsSeries(kind, 14) });
  const hasData = q.data?.series.some((p) => p.value > 0);
  const total = q.data?.series.reduce((s, p) => s + p.value, 0) ?? 0;

  return (
    <Card
      interactive
      glow="blue"
      className="overflow-hidden opacity-0 animate-slide-up"
      style={{ animationDelay: `${delay * 80}ms`, animationFillMode: "forwards" }}
    >
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-2" style={{ color }}>
              <Icon className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h2>
              <p className="text-xs text-[var(--text-muted)]">{desc}</p>
            </div>
          </div>
          <Badge tone="default">14 days</Badge>
        </div>
        {hasData && (
          <p className="metric mt-3 text-2xl font-semibold" style={{ color }}>
            {formatNumber(total)}
            <span className="ml-2 text-xs font-normal text-[var(--text-muted)]">total events</span>
          </p>
        )}
      </CardHeader>
      <CardBody className="pt-0">
        {q.isLoading ? (
          <Skeleton className="h-52 rounded-lg" />
        ) : q.error ? (
          <ErrorState message="Could not load series." onRetry={() => q.refetch()} />
        ) : !hasData ? (
          <EmptyState title="Not enough data yet" hint="Activity will appear here as it accrues." />
        ) : (
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={q.data!.series} margin={{ left: -16, right: 8, top: 8, bottom: 0 }}>
                <defs>
                  <linearGradient id={`g-${kind.replace(/\./g, "-")}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={color} stopOpacity={0.45} />
                    <stop offset="100%" stopColor={color} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#64748b", fontSize: 10 }}
                  tickFormatter={(d) => d.slice(5)}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: "#64748b", fontSize: 10 }}
                  allowDecimals={false}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    background: "rgba(15, 23, 42, 0.95)",
                    border: "1px solid rgba(255,255,255,0.1)",
                    borderRadius: 10,
                    fontSize: 12,
                    backdropFilter: "blur(8px)",
                  }}
                  labelStyle={{ color: "#9aa8bd" }}
                />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke={color}
                  fill={`url(#g-${kind.replace(/\./g, "-")})`}
                  strokeWidth={2.5}
                  dot={false}
                  activeDot={{ r: 4, fill: color, stroke: "#fff", strokeWidth: 1 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

export default function AnalyticsPage() {
  const summary = useQuery({ queryKey: ["analytics-summary"], queryFn: api.analyticsSummary });

  return (
    <div className="mx-auto max-w-6xl animate-fade-in">
      <PageHeader
        title="Analytics"
        description="Computed from your real event stream — never synthetic. Every number traces back to append-only analytics events."
      />

      {summary.isLoading ? (
        <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-[120px] rounded-[var(--radius)]" />
          ))}
        </div>
      ) : summary.data ? (
        <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-3">
          <MetricCard
            label="Memories created"
            value={formatNumber(summary.data.memory_created_total)}
            icon={Layers}
            tone="blue"
            delay={0}
          />
          <MetricCard
            label="Retrievals"
            value={formatNumber(summary.data.retrieval_total)}
            icon={Database}
            tone="cyan"
            delay={1}
          />
          <MetricCard
            label="API requests"
            value={formatNumber(summary.data.api_request_total)}
            icon={Activity}
            tone="purple"
            delay={2}
          />
        </div>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-2">
        <ChartCard
          kind="memory.created"
          title="Memory Growth"
          desc="Memories written per day."
          color="#3b82f6"
          icon={TrendingUp}
          delay={3}
        />
        <ChartCard
          kind="retrieval"
          title="Retrieval Volume"
          desc="Search and context requests per day."
          color="#22d3ee"
          icon={Database}
          delay={4}
        />
      </div>

      <Card className="mt-6 border-[var(--accent-purple)]/20 bg-[var(--accent-purple)]/5 p-4">
        <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
          <span className="font-semibold text-[var(--accent-purple)]">Zero fake data.</span>{" "}
          Charts render only when the analytics pipeline has recorded real events. Empty states are honest — not placeholders.
        </p>
      </Card>
    </div>
  );
}

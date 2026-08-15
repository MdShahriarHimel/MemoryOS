"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity, BookOpen, Code2, ExternalLink, FileJson, Gauge, Terminal, Wrench,
} from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";

import { api } from "@/lib/api/client";

const API_BASE = process.env.NEXT_PUBLIC_MEMORY_OS_API_URL ?? "http://localhost:8000";

function LinkRow({ label, href, note, external = true }: { label: string; href: string; note?: string; external?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 px-4 py-3 text-sm transition-colors hover:bg-[var(--surface-2)]/50">
      <span className="font-medium capitalize text-[var(--text-primary)]">{label}</span>
      {note ? (
        <code className="mono truncate text-xs text-[var(--text-muted)]">{note}</code>
      ) : external ? (
        <a
          href={href}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-xs text-[var(--accent-blue)] hover:underline"
        >
          Open <ExternalLink className="h-3 w-3" />
        </a>
      ) : (
        <Link href={href} className="text-xs text-[var(--accent-blue)] hover:underline">
          Open →
        </Link>
      )}
    </div>
  );
}

export default function DeveloperPage() {
  const portal = useQuery({ queryKey: ["developer-portal"], queryFn: () => api.getDeveloperPortal() });

  if (portal.isLoading) return <LoadingState label="Loading developer portal" />;
  if (portal.error) {
    return (
      <ErrorState
        message={`Developer portal unavailable: ${portal.error.message}`}
        onRetry={() => portal.refetch()}
      />
    );
  }
  if (!portal.data) return null;

  const p = portal.data;
  const sections = [
    {
      title: "Documentation",
      icon: BookOpen,
      color: "var(--accent-blue)",
      items: [
        { label: "Swagger UI", href: `${API_BASE}${p.docs}` },
        { label: "ReDoc", href: `${API_BASE}${p.redoc}` },
        { label: "OpenAPI JSON", href: `${API_BASE}${p.openapi}` },
      ],
    },
    {
      title: "SDKs",
      icon: Code2,
      color: "var(--accent-purple)",
      items: Object.entries(p.sdks).map(([k, v]) => ({ label: k, href: "#", note: v })),
    },
    {
      title: "Operations",
      icon: Wrench,
      color: "var(--accent-cyan)",
      items: Object.entries(p.operations).map(([k, v]) => ({ label: k, href: `${API_BASE}${v}` })),
    },
    ...(p.v03
      ? [{
          title: "v0.3 APIs",
          icon: FileJson,
          color: "var(--ok)",
          items: Object.entries(p.v03).map(([k, v]) => ({ label: k.replace(/_/g, " "), href: `${API_BASE}${v}` })),
        }]
      : []),
    {
      title: "Observability",
      icon: Activity,
      color: "var(--warn)",
      items: Object.entries(p.observability).map(([k, v]) => ({ label: k, href: `${API_BASE}${v}` })),
    },
  ];

  return (
    <div className="mx-auto max-w-4xl animate-fade-in">
      <PageHeader
        title="Developer Portal"
        description="API docs, SDK paths, operational endpoints, and observability hooks."
        action={<Badge tone="purple">v0.3</Badge>}
      />

      <Card className="mb-8 overflow-hidden" glow="blue">
        <div className="border-b border-[var(--border)] bg-gradient-to-r from-[var(--accent-blue)]/10 to-[var(--accent-purple)]/5 px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-2 text-[var(--accent-blue)]">
              <Terminal className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold text-[var(--text-primary)]">CLI install</p>
              <code className="mono mt-0.5 block text-xs text-[var(--text-muted)]">{p.cli}</code>
            </div>
          </div>
        </div>
        <CardBody className="flex flex-wrap gap-2 pt-4">
          {Object.entries(p.authentication).map(([k, v]) => (
            <Badge key={k} tone="default">
              {k}: <span className="mono ml-1">{v}</span>
            </Badge>
          ))}
        </CardBody>
      </Card>

      <div className="grid gap-6">
        {sections.map((s, i) => {
          const Icon = s.icon;
          return (
            <Card
              key={s.title}
              interactive
              className="overflow-hidden opacity-0 animate-slide-up"
              style={{ animationDelay: `${i * 60}ms`, animationFillMode: "forwards" }}
            >
              <CardHeader>
                <h2 className="flex items-center gap-2 text-sm font-semibold">
                  <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-1.5" style={{ color: s.color }}>
                    <Icon className="h-4 w-4" />
                  </div>
                  {s.title}
                </h2>
              </CardHeader>
              <CardBody className="pt-0">
                {s.items.length === 0 ? (
                  <EmptyState title="Nothing listed" />
                ) : (
                  <div className="divide-y divide-[var(--border)] rounded-lg border border-[var(--border)] bg-[var(--surface-2)]/30">
                    {s.items.map((it) => (
                      <LinkRow key={it.label} label={it.label} href={it.href} note={"note" in it ? it.note : undefined} />
                    ))}
                  </div>
                )}
              </CardBody>
            </Card>
          );
        })}
      </div>

      <div className="mt-8 flex justify-center">
        <Button
          variant="secondary"
          onClick={() => window.open(`${API_BASE}${p.docs}`, "_blank", "noopener,noreferrer")}
        >
          <Gauge className="h-4 w-4" />
          Open Swagger UI
        </Button>
      </div>
    </div>
  );
}

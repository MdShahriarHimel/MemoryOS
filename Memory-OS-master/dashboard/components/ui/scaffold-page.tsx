"use client";

import { LucideIcon } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";

export function ScaffoldPage({
  title,
  description,
  icon: Icon,
  hint,
  apiPath,
  links = [],
}: {
  title: string;
  description: string;
  icon: LucideIcon;
  hint: string;
  apiPath?: string;
  links?: { label: string; href: string }[];
}) {
  return (
    <div className="mx-auto max-w-3xl animate-fade-in">
      <PageHeader
        title={title}
        description={description}
        action={<Badge tone="warn">Coming soon</Badge>}
      />

      <Card glow="purple" className="overflow-hidden">
        <CardBody className="py-16 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-[var(--border)] bg-gradient-to-br from-[var(--accent-purple)]/20 to-[var(--accent-blue)]/10 text-[var(--accent-purple)]">
            <Icon className="h-7 w-7" />
          </div>
          <p className="text-sm font-medium text-[var(--text-primary)]">{title} is scaffolded</p>
          <p className="mx-auto mt-2 max-w-md text-xs leading-relaxed text-[var(--text-muted)]">{hint}</p>
          {apiPath && (
            <p className="mono mt-4 text-[11px] text-[var(--text-secondary)]">
              API: <span className="text-[var(--accent-cyan)]">{apiPath}</span>
            </p>
          )}
          {links.length > 0 && (
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {links.map((l) => (
                <Link key={l.href} href={l.href}>
                  <Button variant="secondary" size="sm">{l.label}</Button>
                </Link>
              ))}
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";
import { Building2, Key, Shield, User } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { api, ApiError } from "@/lib/api/client";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";

export default function OrganizationSettingsPage() {
  const me = useQuery({
    queryKey: ["auth-me"],
    queryFn: () => api.me(),
    enabled: true,
    retry: false,
  });

  const unauthenticated = me.error instanceof ApiError && me.error.status === 401;

  return (
    <div className="mx-auto max-w-3xl animate-fade-in">
      <PageHeader
        title="Organization"
        description="Tenant and organization context for your MEMORY OS deployment."
      />

      {me.isLoading ? (
        <LoadingState label="Loading organization" />
      ) : unauthenticated || (!me.data && !me.isLoading) ? (
        <Card glow="purple">
          <CardBody>
            <EmptyState
              title="Sign in to view organization"
              hint="Local anon mode uses X-Tenant-ID / demo-tenant without a user profile."
              icon={Building2}
            />
            <div className="flex justify-center gap-2 pb-6">
              <Link href="/login"><Button variant="secondary">Sign in</Button></Link>
              <Link href="/settings/security"><Button variant="ghost">Security</Button></Link>
            </div>
          </CardBody>
        </Card>
      ) : me.error ? (
        <ErrorState message="Could not load organization profile." onRetry={() => me.refetch()} />
      ) : me.data ? (
        <div className="space-y-4">
          <Card interactive>
            <CardHeader>
              <h2 className="flex items-center gap-2 text-sm font-semibold">
                <User className="h-4 w-4 text-[var(--accent-blue)]" />
                Signed-in user
              </h2>
            </CardHeader>
            <CardBody className="space-y-3 pt-0">
              <div className="flex items-center justify-between text-sm">
                <span className="text-[var(--text-muted)]">Email</span>
                <span>{me.data.email}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-[var(--text-muted)]">Role</span>
                <Badge tone="purple">{me.data.role}</Badge>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-[var(--text-muted)]">Organization ID</span>
                <code className="mono text-xs">{me.data.organization_id}</code>
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardBody className="flex flex-wrap gap-2">
              <Link href="/api-keys"><Button variant="secondary" size="sm"><Key className="h-3.5 w-3.5" /> API Keys</Button></Link>
              <Link href="/settings/security"><Button variant="secondary" size="sm"><Shield className="h-3.5 w-3.5" /> Security</Button></Link>
            </CardBody>
          </Card>
        </div>
      ) : null}
    </div>
  );
}

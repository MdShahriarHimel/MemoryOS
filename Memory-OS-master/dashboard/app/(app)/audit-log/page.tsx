"use client";

import { useQuery } from "@tanstack/react-query";
import { ScrollText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { api } from "@/lib/api/client";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";

export default function AuditLogPage() {
  const logs = useQuery({
    queryKey: ["audit-logs"],
    queryFn: () => api.listAuditLogs({ limit: 100 }),
  });

  if (logs.isLoading) return <LoadingState label="Loading audit log…" />;
  if (logs.isError) return <ErrorState message="Could not load audit logs." onRetry={() => logs.refetch()} />;

  const items = logs.data ?? [];

  return (
    <div>
      <PageHeader
        title="Audit Log"
        description="Append-only trail of mutating API calls for compliance and forensics."
      />
      {items.length === 0 ? (
        <EmptyState
          icon={ScrollText}
          title="No audit entries yet"
          hint="Mutating API requests will appear here once activity begins."
        />
      ) : (
        <Card>
          <CardBody className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] text-left text-[var(--text-muted)]">
                    <th className="px-4 py-3 font-medium">Time</th>
                    <th className="px-4 py-3 font-medium">Action</th>
                    <th className="px-4 py-3 font-medium">Actor</th>
                    <th className="px-4 py-3 font-medium">Result</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((row) => (
                    <tr key={row.id} className="border-b border-[var(--border)] last:border-0">
                      <td className="px-4 py-3 whitespace-nowrap text-[var(--text-secondary)]">
                        {new Date(row.at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">{row.action}</td>
                      <td className="px-4 py-3">{row.actor ?? "—"}</td>
                      <td className="px-4 py-3">
                        <Badge tone={row.result === "success" ? "success" : "warning"}>{row.result}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  );
}

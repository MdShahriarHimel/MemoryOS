"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, Play } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { api } from "@/lib/api/client";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";

export default function BenchmarksPage() {
  const qc = useQueryClient();
  const runs = useQuery({
    queryKey: ["benchmark-runs"],
    queryFn: () => api.listBenchmarkRuns(),
  });

  const runBench = useMutation({
    mutationFn: () => api.runBenchmark({ name: "dashboard-run", scale: 1000 }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["benchmark-runs"] }),
  });

  if (runs.isLoading) return <LoadingState label="Loading benchmark runs…" />;
  if (runs.isError) return <ErrorState message="Could not load benchmarks." onRetry={() => runs.refetch()} />;

  const items = runs.data ?? [];

  return (
    <div>
      <PageHeader
        title="MemoryBench"
        description="Deterministic benchmark suite — real measurements, no fabricated scores."
        action={
          <Button onClick={() => runBench.mutate()} disabled={runBench.isPending}>
            <Play className="mr-2 h-4 w-4" />
            Run suite
          </Button>
        }
      />
      {items.length === 0 ? (
        <EmptyState
          icon={FlaskConical}
          title="No benchmark runs yet"
          hint="Run MemoryBench to validate retrieval, truth, and isolation categories."
        />
      ) : (
        <div className="space-y-4">
          {items.map((run) => (
            <Card key={run.id}>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <p className="font-medium">{run.name}</p>
                  <p className="text-xs text-[var(--text-muted)]">{new Date(run.created_at).toLocaleString()}</p>
                </div>
                <Badge tone={run.status === "completed" ? "success" : "default"}>{run.status}</Badge>
              </CardHeader>
              <CardBody>
                <pre className="max-h-64 overflow-auto rounded-lg bg-[var(--surface-elevated)] p-3 text-xs">
                  {JSON.stringify(run.results, null, 2)}
                </pre>
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

import { Skeleton } from "@/components/ui/states";

export default function AppLoading() {
  return (
    <div className="mx-auto max-w-6xl animate-fade-in space-y-6 p-2">
      <Skeleton className="h-10 w-64 rounded-lg" />
      <Skeleton className="h-4 w-96 rounded" />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-[120px] rounded-[var(--radius)]" />
        ))}
      </div>
    </div>
  );
}

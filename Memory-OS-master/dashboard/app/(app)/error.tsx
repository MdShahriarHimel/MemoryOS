"use client";
export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="p-8">
      <p className="text-sm text-[var(--text-secondary)]">Something went wrong rendering this page.</p>
      <button onClick={reset} className="mt-3 rounded-md border border-[var(--border)] px-3 py-1.5 text-xs">Try again</button>
    </div>
  );
}

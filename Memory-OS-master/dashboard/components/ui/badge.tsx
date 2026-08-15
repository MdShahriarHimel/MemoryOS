import { cn } from "@/lib/utils";

const TONE: Record<string, string> = {
  default: "border-[var(--border)] bg-[var(--surface-2)] text-[var(--text-secondary)]",
  blue: "border-[var(--accent-blue)]/30 bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]",
  purple: "border-[var(--accent-purple)]/30 bg-[var(--accent-purple)]/10 text-[var(--accent-purple)]",
  cyan: "border-[var(--accent-cyan)]/30 bg-[var(--accent-cyan)]/10 text-[var(--accent-cyan)]",
  ok: "border-[var(--ok)]/30 bg-[var(--ok)]/10 text-[var(--ok)]",
  warn: "border-[var(--warn)]/30 bg-[var(--warn)]/10 text-[var(--warn)]",
};

export function Badge({
  children,
  tone = "default",
  className,
}: {
  children: React.ReactNode;
  tone?: keyof typeof TONE;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium capitalize",
        TONE[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

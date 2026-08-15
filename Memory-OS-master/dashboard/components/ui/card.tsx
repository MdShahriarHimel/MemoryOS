import { cn } from "@/lib/utils";

export function Card({
  children,
  className,
  interactive,
  glow,
  style,
}: {
  children: React.ReactNode;
  className?: string;
  interactive?: boolean;
  glow?: "blue" | "purple" | "cyan";
  style?: React.CSSProperties;
}) {
  return (
    <div
      style={style}
      className={cn(
        "rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface-1)]/80 backdrop-blur-sm",
        interactive && "card-interactive cursor-default",
        glow === "blue" && "hover:shadow-[var(--glow-blue)]",
        glow === "purple" && "hover:shadow-[var(--glow-purple)]",
        glow === "cyan" && "hover:shadow-[var(--glow-cyan)]",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("px-4 pt-4 pb-2", className)}>{children}</div>;
}

export function CardBody({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("px-4 pb-4", className)}>{children}</div>;
}

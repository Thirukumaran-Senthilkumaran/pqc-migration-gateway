import { ReactNode } from "react";
import clsx from "clsx";

interface Props {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  accent?: "default" | "ok" | "warn" | "bad" | "pqc";
}

const accentClasses: Record<NonNullable<Props["accent"]>, string> = {
  default: "border-bg-border",
  ok:      "border-emerald-500/30 shadow-[0_0_24px_rgba(16,185,129,0.15)]",
  warn:    "border-amber-500/30 shadow-[0_0_24px_rgba(245,158,11,0.15)]",
  bad:     "border-red-500/30 shadow-[0_0_24px_rgba(239,68,68,0.15)]",
  pqc:     "border-accent/40 shadow-glow",
};

export default function StatCard({ label, value, hint, icon, accent = "default" }: Props) {
  return (
    <div className={clsx("card p-5 transition-all hover:border-accent/40", accentClasses[accent])}>
      <div className="flex items-start justify-between">
        <div className="stat-label">{label}</div>
        {icon && <div className="text-accent-glow opacity-80">{icon}</div>}
      </div>
      <div className="stat-value mt-2">{value}</div>
      {hint && <div className="text-xs text-muted mt-1">{hint}</div>}
    </div>
  );
}

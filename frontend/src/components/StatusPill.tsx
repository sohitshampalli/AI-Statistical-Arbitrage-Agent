import { AlertTriangle, Check, CircleDashed, FlaskConical, Database, ShieldCheck, X, type LucideIcon } from "lucide-react";
import { cx } from "../lib/cx";

export type PillKind =
  | "pass"
  | "fail"
  | "warn"
  | "synthetic"
  | "real"
  | "paper"
  | "exploratory"
  | "neutral";

const STYLES: Record<PillKind, { icon: LucideIcon; className: string }> = {
  pass: { icon: Check, className: "text-positive border-positive/35 bg-positive/10" },
  fail: { icon: X, className: "text-negative border-negative/35 bg-negative/10" },
  warn: { icon: AlertTriangle, className: "text-alert border-alert/40 bg-alert/10" },
  synthetic: { icon: FlaskConical, className: "text-accent border-accent/45 bg-accent/10" },
  real: { icon: Database, className: "text-ink border-line-strong bg-glass" },
  paper: { icon: ShieldCheck, className: "text-ink-2 border-line-strong bg-glass" },
  exploratory: { icon: CircleDashed, className: "text-alert border-alert/40 bg-transparent" },
  neutral: { icon: CircleDashed, className: "text-ink-2 border-line bg-glass" },
};

/** A state shown with an icon and words, never by colour alone. */
export function StatusPill({ kind, children, className, title, subtle }: { kind: PillKind; children: string; className?: string; title?: string; subtle?: boolean }) {
  const { icon: Icon, className: tone } = STYLES[kind];
  if (subtle) {
    const ink = tone.split(" ")[0];
    return (
      <span title={title} className={cx("inline-flex items-center gap-1.5 text-[13px] whitespace-nowrap text-ink-2", className)}>
        <Icon aria-hidden size={13} strokeWidth={2.25} className={ink} />
        {children}
      </span>
    );
  }
  const upper = kind === "synthetic" || kind === "real" || kind === "exploratory";
  return (
    <span
      title={title}
      className={cx(
        "inline-flex h-6 items-center gap-1.5 rounded-full border px-2.5 text-[12px] leading-none font-medium whitespace-nowrap",
        upper && "tracking-[0.06em] uppercase",
        tone,
        className,
      )}
    >
      <Icon aria-hidden size={13} strokeWidth={2} />
      {children}
    </span>
  );
}

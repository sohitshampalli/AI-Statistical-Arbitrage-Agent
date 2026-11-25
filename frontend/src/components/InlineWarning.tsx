import { AlertTriangle, Clock3, FileWarning, Info, Users } from "lucide-react";
import type { ReactNode } from "react";
import { cx } from "../lib/cx";

export type WarningKind = "survivorship" | "small_sample" | "regime_break" | "stale" | "terms" | "exploratory" | "info";

const ICONS = {
  survivorship: Users,
  small_sample: AlertTriangle,
  regime_break: AlertTriangle,
  stale: Clock3,
  terms: FileWarning,
  exploratory: AlertTriangle,
  info: Info,
} as const;

const TITLES: Record<WarningKind, string> = {
  survivorship: "Survivorship bias",
  small_sample: "Small sample",
  regime_break: "Regime break",
  stale: "Stale result",
  terms: "Data terms",
  exploratory: "Exploratory",
  info: "Note",
};

/** A short warning beside the result it qualifies. Alert colour plus icon plus title. */
export function InlineWarning({ kind, children, className }: { kind: WarningKind; children: ReactNode; className?: string }) {
  const Icon = ICONS[kind];
  const tone = kind === "info" || kind === "stale" ? "border-line-strong text-ink-2" : "border-alert/35 text-ink-2";
  const iconTone = kind === "info" || kind === "stale" ? "text-ink-2" : "text-alert";
  return (
    <div role="note" className={cx("flex gap-3 rounded-[var(--radius-control)] border bg-glass px-4 py-3", tone, className)}>
      <Icon aria-hidden size={16} className={cx("mt-0.5 shrink-0", iconTone)} />
      <p className="t-body">
        <span className="font-medium text-ink">{TITLES[kind]}. </span>
        {children}
      </p>
    </div>
  );
}

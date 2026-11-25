import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import type { ReactNode } from "react";
import type { ProvenanceInfo } from "../context/project";
import { cx } from "../lib/cx";
import { GlassCard } from "./GlassCard";
import { ProvenanceHover } from "./ProvenanceHover";
import { Skeleton } from "./Skeleton";

interface KpiCardProps {
  label: string;
  /** Formatted value. null means no value exists; `emptyText` says why. */
  value: string | null;
  unit?: string;
  delta?: { text: string; direction: "up" | "down" | "flat"; good: boolean | null };
  aside?: ReactNode;
  /** Pills shown under the label, for example Exploratory. */
  pills?: ReactNode;
  footnote?: ReactNode;
  emptyText?: string;
  provenance?: ProvenanceInfo;
  loading?: boolean;
  glow?: boolean;
  className?: string;
}

/** A label, one large number and its context. */
export function KpiCard({ label, value, unit, delta, aside, pills, footnote, emptyText, provenance, loading, glow, className }: KpiCardProps) {
  const DeltaIcon = delta?.direction === "up" ? ArrowUpRight : delta?.direction === "down" ? ArrowDownRight : Minus;
  const tone = delta?.good === true ? "text-positive" : delta?.good === false ? "text-negative" : "text-ink-2";
  const number = <span className="t-kpi text-ink">{value}</span>;
  return (
    <GlassCard glow={glow} className={cx("flex min-h-[156px] flex-col", className)}>
      <div className="flex items-start justify-between gap-3">
        <p className="t-label text-ink-2">{label}</p>
        {aside}
      </div>
      {pills && <div className="mt-2 flex flex-wrap gap-2">{pills}</div>}
      <div className="mt-4 flex flex-1 items-end gap-2">
        {loading ? (
          <Skeleton className="h-10 w-32" />
        ) : value === null ? (
          <p className="t-h3 max-w-[28ch] font-normal text-ink-2">{emptyText ?? "No value"}</p>
        ) : (
          <>
            {provenance ? <ProvenanceHover info={provenance}>{number}</ProvenanceHover> : number}
            {unit && <span className="t-body mb-1.5 text-ink-2">{unit}</span>}
          </>
        )}
      </div>
      {(delta || footnote) && !loading && (
        <div className="t-body mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-ink-2">
          {delta && (
            <span className={cx("inline-flex items-center gap-1 font-medium", tone)}>
              <DeltaIcon aria-hidden size={14} />
              {delta.text}
            </span>
          )}
          {footnote}
        </div>
      )}
    </GlassCard>
  );
}

import { useState, type ReactNode } from "react";
import { GlassCard } from "./GlassCard";
import { SegmentedToggle } from "./SegmentedToggle";

interface ChartCardProps {
  /** States the finding, not the chart type. */
  title: string;
  /** Period, sample size and cost assumption. */
  subtitle: string;
  /** Data source. */
  source: ReactNode;
  children: ReactNode;
  /** The same data as a table, for keyboard and screen-reader users. */
  table?: ReactNode;
  actions?: ReactNode;
  pills?: ReactNode;
  glow?: boolean;
  className?: string;
}

/** A chart with a finding as its title, its assumptions and its source. */
export function ChartCard({ title, subtitle, source, children, table, actions, pills, glow, className }: ChartCardProps) {
  const [view, setView] = useState<"chart" | "table">("chart");
  return (
    <GlassCard glow={glow} className={className}>
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0 max-w-[96ch]">
          {pills && <div className="mb-2 flex flex-wrap gap-2">{pills}</div>}
          <h3 className="t-h2 text-ink">{title}</h3>
          <p className="t-body mt-1 text-ink-2">{subtitle}</p>
        </div>
        <div className="flex items-center gap-2">
          {actions}
          {table && (
            <SegmentedToggle
              label="Chart or table"
              value={view}
              onChange={setView}
              options={[
                { value: "chart", label: "Chart" },
                { value: "table", label: "Table" },
              ]}
            />
          )}
        </div>
      </header>
      <div className="mt-5">{view === "chart" || !table ? children : table}</div>
      <footer className="t-body mt-4 border-t border-line pt-3 text-ink-3">Source: {source}</footer>
    </GlassCard>
  );
}

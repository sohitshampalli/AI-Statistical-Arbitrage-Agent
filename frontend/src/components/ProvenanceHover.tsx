import { useId, useState, type ReactNode } from "react";
import { useProject, type ProvenanceInfo } from "../context/project";
import { bps, shortHash } from "../lib/format";
import { cx } from "../lib/cx";

/**
 * Wrap a number so hover or focus shows where it came from; click opens the
 * full "About this result" drawer.
 */
export function ProvenanceHover({ info, children, className }: { info: ProvenanceInfo; children: ReactNode; className?: string }) {
  const { openProvenance } = useProject();
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span className="relative inline-flex" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        aria-describedby={open ? id : undefined}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => openProvenance(info)}
        className={cx("cursor-help rounded-[4px] text-left decoration-line-strong decoration-dotted underline-offset-[6px] hover:underline", className)}
      >
        {children}
      </button>
      {open && (
        <span
          id={id}
          role="tooltip"
          className="t-num pointer-events-none absolute top-full left-0 z-40 mt-2 w-[300px] rounded-[10px] border border-line-strong bg-bg-2 px-3.5 py-3 text-ink-2 shadow-[0_12px_32px_rgba(0,0,0,0.5)]"
        >
          <span className="t-label block text-ink-2">{info.label}</span>
          <span className="mt-2 grid grid-cols-[72px_1fr] gap-x-3 gap-y-1">
            {info.runId && (<><span className="text-ink-3">run</span><span className="truncate text-ink">{info.runId}</span></>)}
            <span className="text-ink-3">commit</span>
            <span className="text-ink">{shortHash(info.provenance.code_commit)}</span>
            {info.span && (<><span className="text-ink-3">span</span><span className="text-ink">{info.span}</span></>)}
            {info.costBps !== undefined && info.costBps !== null && (<><span className="text-ink-3">cost</span><span className="text-ink">{bps(info.costBps)}</span></>)}
            {info.provenance.config_hashes.backtest && (<><span className="text-ink-3">config</span><span className="text-ink">{info.provenance.config_hashes.backtest.slice(0, 10)}</span></>)}
          </span>
          <span className="mt-2 block text-ink-3">Click for full provenance</span>
        </span>
      )}
    </span>
  );
}

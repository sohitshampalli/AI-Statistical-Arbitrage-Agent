import { Layers } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { useProject } from "../context/project";
import { count } from "../lib/format";
import { Skeleton } from "./Skeleton";

// Trial log lines 9 to 97: the milestone B demo run, recorded dirty because
// the trial log itself was counted as code (docs/STATUS.md).
const KNOWN_DIRTY = Array.from({ length: 89 }, (_, i) => i + 9);

/** "97 trials logged, 57 counted": every try is on the record, and the count is visible. */
export function TrialCountBadge() {
  const { trials, meta } = useProject();
  const [open, setOpen] = useState(false);
  const id = useId();
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (box.current && !box.current.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (trials.status === "loading") return <Skeleton className="h-8 w-48 rounded-full" />;
  if (trials.status === "error") return <span className="t-body text-negative">Trial log unreadable</span>;
  const stats = trials.data;
  const stale = meta.status === "ready" && meta.data.summary_stale;
  return (
    <div className="relative" ref={box}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((v) => !v)}
        className="t-num inline-flex h-8 items-center gap-2 rounded-full border border-line-strong bg-glass px-3 text-ink-2 transition-colors duration-150 hover:bg-glass-hover hover:text-ink"
      >
        <Layers aria-hidden size={14} />
        <span>
          <span className="text-ink">{count(stats.n_lines)}</span> trials logged
          <span className="mx-1.5 text-ink-3">/</span>
          <span className="text-ink">{count(stats.n_counted)}</span> counted
        </span>
      </button>
      {open && (
        <div id={id} role="dialog" aria-label="Trial log" className="absolute top-full right-0 z-40 mt-2 w-[380px] rounded-[12px] border border-line-strong bg-bg-1 p-5 shadow-[0_16px_48px_rgba(0,0,0,0.55)]">
          <p className="t-label text-ink-2">Trial log</p>
          <p className="t-body mt-2 text-ink-2">{stats.counting_rule}</p>
          <dl className="t-num mt-4 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1.5">
            <dt className="text-ink-3">lines in trials/trials.jsonl</dt>
            <dd className="text-right text-ink">{count(stats.n_lines)}</dd>
            <dt className="text-ink-3">real backtests counted</dt>
            <dd className="text-right text-ink">{count(stats.n_backtests_counted)}</dd>
            <dt className="text-ink-3">candidates screened, not backtested</dt>
            <dd className="text-right text-ink">{count(stats.n_screened_not_backtested)}</dd>
            <dt className="text-ink-2">N for the Deflated Sharpe</dt>
            <dd className="text-right font-medium text-ink">{count(stats.n_counted)}</dd>
          </dl>
          <p className="t-label mt-5 text-ink-3">By kind</p>
          <dl className="t-num mt-2 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1">
            {Object.entries(stats.by_kind).map(([kind, n]) => (
              <div key={kind} className="contents">
                <dt className="text-ink-3">{kind.replace("_", " ")}</dt>
                <dd className="text-right text-ink">{count(n)}</dd>
              </div>
            ))}
          </dl>
          {stats.dirty_lines.length > 0 && (
            <p className="t-body mt-4 text-ink-3">
              {count(stats.dirty_lines.length)} {stats.dirty_lines.length === 1 ? "line records" : "lines record"} the code as dirty.
              {KNOWN_DIRTY.every((n) => stats.dirty_lines.includes(n)) &&
                " Lines 9 to 97 do so although the code was clean: a known provenance defect, fixed on 2026-11-23 and documented in docs/STATUS.md. The lines are not edited."}
            </p>
          )}
          {stale && (
            <p className="t-body mt-3 text-alert">The stored summary used fewer trials than the log counts now. Run `uv run statarb summarise` (adds no trial).</p>
          )}
        </div>
      )}
    </div>
  );
}

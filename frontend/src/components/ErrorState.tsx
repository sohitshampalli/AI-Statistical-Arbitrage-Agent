import { CircleAlert } from "lucide-react";
import type { ApiFailure } from "../api/client";
import { cx } from "../lib/cx";

/** A plain message with the failing endpoint and run id (spec section 9). */
export function ErrorState({ failure, title = "This result could not be loaded", className }: { failure: ApiFailure; title?: string; className?: string }) {
  return (
    <div role="alert" className={cx("flex gap-3 rounded-[var(--radius-control)] border border-negative/35 bg-negative/[0.06] px-4 py-4", className)}>
      <CircleAlert aria-hidden size={18} className="mt-0.5 shrink-0 text-negative" />
      <div className="min-w-0">
        <p className="t-h3 text-ink">{title}</p>
        <p className="t-body mt-1 text-ink-2">{failure.status === 0 ? "The dashboard server did not answer. Is `uv run statarb dashboard` still running?" : failure.message}</p>
        <dl className="t-num mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-ink-3">
          <dt>endpoint</dt>
          <dd className="truncate text-ink-2">{failure.endpoint}</dd>
          <dt>status</dt>
          <dd className="text-ink-2">{failure.status === 0 ? "no answer" : `${failure.status} ${failure.body?.error ?? ""}`}</dd>
          {failure.runId && (
            <>
              <dt>run id</dt>
              <dd className="truncate text-ink-2">{failure.runId}</dd>
            </>
          )}
        </dl>
      </div>
    </div>
  );
}

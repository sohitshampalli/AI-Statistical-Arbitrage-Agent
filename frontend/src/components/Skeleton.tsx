import { cx } from "../lib/cx";

/** A loading placeholder in the shape of the content it stands for. */
export function Skeleton({ className, label = "Loading" }: { className?: string; label?: string }) {
  return <span role="status" aria-label={label} className={cx("skeleton-shimmer block rounded-[8px]", className)} />;
}

export function SkeletonLines({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cx("flex flex-col gap-2.5", className)} role="status" aria-label="Loading">
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className="skeleton-shimmer block h-3 rounded-[6px]" style={{ width: `${92 - i * 17}%` }} />
      ))}
    </div>
  );
}

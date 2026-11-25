import { cx } from "../lib/cx";

interface Option<T extends string> {
  value: T;
  label: string;
}

/** A small segmented control (for example 2D / 3D, or chart / table). */
export function SegmentedToggle<T extends string>({ options, value, onChange, label }: { options: Option<T>[]; value: T; onChange: (value: T) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-[var(--radius-control)] border border-line bg-bg-1 p-0.5">
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(option.value)}
            className={cx(
              "t-body h-7 rounded-[8px] px-3 transition-colors duration-150",
              active ? "bg-bg-2 text-ink shadow-[inset_0_0_0_1px_var(--border-strong)]" : "text-ink-2 hover:text-ink",
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

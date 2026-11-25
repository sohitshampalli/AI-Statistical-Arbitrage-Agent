import { Check, Copy, Inbox, type LucideIcon } from "lucide-react";
import { useState, type ReactNode } from "react";
import { cx } from "../lib/cx";

interface EmptyStateProps {
  title: string;
  children: ReactNode;
  /** The CLI command that produces the missing result, if there is one. */
  command?: string;
  icon?: LucideIcon;
  className?: string;
}

/** What is missing, why, and which command produces it. Never fake data. */
export function EmptyState({ title, children, command, icon: Icon = Inbox, className }: EmptyStateProps) {
  const [copied, setCopied] = useState(false);
  return (
    <div className={cx("flex flex-col items-start gap-3 rounded-[var(--radius-control)] border border-dashed border-line-strong px-6 py-8", className)}>
      <span className="grid size-9 place-items-center rounded-full border border-line bg-glass text-ink-2">
        <Icon aria-hidden size={17} />
      </span>
      <h3 className="t-h3 text-ink">{title}</h3>
      <div className="t-body max-w-[60ch] text-ink-2">{children}</div>
      {command && (
        <div className="mt-1 flex items-center gap-2 rounded-[8px] border border-line bg-bg-1 py-1.5 pr-1.5 pl-3">
          <code className="t-num text-ink">{command}</code>
          <button
            type="button"
            onClick={() => {
              void navigator.clipboard?.writeText(command).then(() => setCopied(true));
            }}
            className="grid size-7 place-items-center rounded-[6px] text-ink-2 transition-colors duration-150 hover:bg-glass-hover hover:text-ink"
            aria-label={copied ? "Command copied" : "Copy command"}
          >
            {copied ? <Check aria-hidden size={14} /> : <Copy aria-hidden size={14} />}
          </button>
        </div>
      )}
    </div>
  );
}

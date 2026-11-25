import { CheckCircle2, CircleDashed, Loader } from "lucide-react";
import type { Gate } from "../api/types";
import { cx } from "../lib/cx";

/** One phase gate: passed (with date and evidence tests), in progress, or not started. */
export function GateBadge({ gate }: { gate: Gate }) {
  const passed = gate.status === "passed";
  const Icon = passed ? CheckCircle2 : gate.status === "in_progress" ? Loader : CircleDashed;
  return (
    <div className={cx("flex flex-col gap-2 rounded-[12px] border px-4 py-3.5", passed ? "border-positive/25 bg-positive/[0.05]" : "border-line bg-glass")}>
      <div className="flex items-center gap-2">
        <Icon aria-hidden size={16} className={passed ? "text-positive" : gate.status === "in_progress" ? "text-accent" : "text-ink-3"} />
        <span className="t-label text-ink-2">Phase {gate.phase}</span>
        <span className={cx("t-body ml-auto", passed ? "text-positive" : "text-ink-3")}>
          {passed ? `Passed ${gate.passed_on}` : gate.status === "in_progress" ? "In progress" : "Not started"}
        </span>
      </div>
      <p className="t-h3 text-ink">{gate.title}</p>
      <p className="t-body text-ink-2">{gate.gate}</p>
      {gate.evidence.length > 0 && (
        <details className="group">
          <summary className="t-body cursor-pointer text-ink-3 hover:text-ink-2">
            {gate.evidence.length} evidence {gate.evidence.length === 1 ? "test" : "tests"}
          </summary>
          <ul className="t-num mt-2 flex flex-col gap-1 text-ink-2">
            {gate.evidence.map((node) => (
              <li key={node} className="break-all">{node}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

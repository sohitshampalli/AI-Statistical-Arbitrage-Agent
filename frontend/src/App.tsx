// Application shell. Pages arrive in later commits; until then the shell
// shows the live project state from /api/meta, so the wiring is visible.
import type { Meta } from "./api/types";
import { useApi } from "./api/useApi";
import { isoDate, shortHash } from "./lib/format";

export function App() {
  const meta = useApi<Meta>("/api/meta");
  return (
    <main className="mx-auto max-w-[var(--page-max)] px-6 py-12">
      <p className="t-label text-ink-2">statarb-agent</p>
      <h1 className="t-display mt-2">Research dashboard</h1>
      {meta.status === "loading" && <p className="t-body mt-6 text-ink-2">Loading project state.</p>}
      {meta.status === "error" && (
        <p className="t-body mt-6 text-alert" role="alert">
          {meta.failure.message} ({meta.failure.endpoint})
        </p>
      )}
      {meta.status === "ready" && (
        <p className="t-num mt-6 text-ink-2">
          commit {shortHash(meta.data.head_commit)}, data {isoDate(meta.data.data_first_date)} to{" "}
          {isoDate(meta.data.data_last_date)}, {meta.data.trials_in_log} trials logged
        </p>
      )}
    </main>
  );
}

// Project-wide state loaded once: /api/meta, /api/data and /api/trials/stats.
// The provenance drawer reads snapshot dates and the data-terms note from here.
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { DataProvenance, Meta, Provenance, Period, TrialStats } from "../api/types";
import { useApi, type ApiState } from "../api/useApi";

export interface ProvenanceInfo {
  /** What the number is, in words: "Validation net Sharpe, HD / LOW". */
  label: string;
  runId?: string | null;
  kind?: string | null;
  createdAt?: string | null;
  provenance: Provenance;
  period?: Period | null;
  span?: string | null;
  costBps?: number | null;
  /** Trials behind a Deflated Sharpe ratio, and where that count comes from. */
  trialsN?: number | null;
  trialsNote?: string | null;
  dataSource?: string | null;
  stale?: boolean;
  label2?: string | null;
}

interface ProjectContextValue {
  meta: ApiState<Meta>;
  data: ApiState<DataProvenance>;
  trials: ApiState<TrialStats>;
  drawer: ProvenanceInfo | null;
  openProvenance: (info: ProvenanceInfo) => void;
  closeProvenance: () => void;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const meta = useApi<Meta>("/api/meta");
  const data = useApi<DataProvenance>("/api/data");
  const trials = useApi<TrialStats>("/api/trials/stats");
  const [drawer, setDrawer] = useState<ProvenanceInfo | null>(null);
  const value = useMemo(
    () => ({ meta, data, trials, drawer, openProvenance: setDrawer, closeProvenance: () => setDrawer(null) }),
    [meta, data, trials, drawer],
  );
  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useProject(): ProjectContextValue {
  const value = useContext(ProjectContext);
  if (value === null) throw new Error("useProject outside ProjectProvider");
  return value;
}

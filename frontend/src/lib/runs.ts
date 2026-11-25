// Small helpers that name runs for display. They read stored fields only.
import type { RunListItem, RunManifest } from "../api/types";

export function pairName(tickers: string[] | null | undefined): string {
  return tickers && tickers.length ? tickers.join(" / ") : "summary";
}

export function hedgeName(hedge: string | null | undefined): string {
  if (!hedge) return "";
  return hedge === "johansen" ? "Johansen basket" : `${hedge} hedge`;
}

export function isSynthetic(run: Pick<RunManifest | RunListItem, "data_source">): boolean {
  return run.data_source === "synthetic";
}

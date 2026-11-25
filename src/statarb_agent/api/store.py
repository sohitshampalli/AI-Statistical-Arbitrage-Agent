"""Read-only access to everything the dashboard shows.

The store reads, never writes: run artifacts in reports/runs (hash-checked
through backtest.runs), the trial log, the configs, configs/pairs.yaml and the
snapshot manifest. It counts and groups what is stored (trials by kind, which
trials count for the Deflated Sharpe ratio) with the same functions the
backtest runner uses; it computes no statistic.

Data provenance. Every price in the project so far comes from Yahoo Finance
through yfinance, downloaded on 2026-11-08 and 2026-11-10, before the terms
were checked on 2026-11-23. New downloads are disabled
(`YFINANCE_DOWNLOADS_ENABLED`). Each snapshot is reported with its source, its
retrieval time and whether it was downloaded before the terms check, so the
dashboard can show it next to every result.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import pandas as pd

from statarb_agent.backtest.runner import (
    counts_for_deflation,
    screen_status,
    screened_not_backtested,
)
from statarb_agent.backtest.runs import list_runs, read_manifest, read_table
from statarb_agent.project import CONFIG_NAMES, Project, load_pairs
from statarb_agent.provenance import file_sha256
from statarb_agent.sources.base import RAW_DIR, Manifest, ManifestEntry
from statarb_agent.sources.prices import SOURCE, YFINANCE_DOWNLOADS_ENABLED
from statarb_agent.trials import Trial, TrialLog


@dataclass(frozen=True)
class SourceInfo:
    """What the project knows about one data source.

    Attributes:
        name: The source name used in the manifest and the trial log.
        title: Human-readable name.
        downloads_enabled: Whether the code may download new data from it.
        terms_checked_on: ISO date the terms were read, or None.
        terms_note: One sentence on the terms situation.
        reference: Where the full record is.
    """

    name: str
    title: str
    downloads_enabled: bool
    terms_checked_on: str | None
    terms_note: str
    reference: str


SOURCES: Final = {
    SOURCE: SourceInfo(
        name=SOURCE,
        title="Yahoo Finance, through the yfinance library",
        downloads_enabled=YFINANCE_DOWNLOADS_ENABLED,
        terms_checked_on="2026-11-23",
        terms_note=(
            "Downloaded before the terms check. Yahoo's Terms of Service "
            "prohibit automated collection without express prior permission, "
            "so new downloads are off pending a licensed data source."
        ),
        reference="docs/THIRD_PARTY.md",
    ),
}


def downloaded_before_terms_check(entry: ManifestEntry) -> bool | None:
    """True if a snapshot was retrieved before its source's terms were read.

    None if the source has no recorded terms check.
    """
    info = SOURCES.get(entry.source)
    if info is None or info.terms_checked_on is None:
        return None
    retrieved = pd.Timestamp(entry.retrieved_at_utc).tz_convert("UTC").tz_localize(None)
    return bool(retrieved < pd.Timestamp(info.terms_checked_on))


class ResultStore:
    """Read-only view of one project folder."""

    def __init__(self, root: Path) -> None:
        self.project = Project(Path(root))

    # Runs -----------------------------------------------------------------

    def runs(self) -> list[dict[str, Any]]:
        """A short record of every stored run, oldest first.

        Each record has run_id, kind, label, tickers, strategy, hedge,
        cost_bps, control, data_source, created_at_utc, code_commit and
        code_dirty (None where a kind does not have the field).
        """
        out = []
        for man in list_runs(self.project.runs_dir):
            prov = man.get("provenance") or {}
            out.append({
                "run_id": man["run_id"],
                "kind": man["kind"],
                "label": man.get("label"),
                "tickers": man.get("tickers"),
                "strategy": man.get("strategy"),
                "hedge": man.get("hedge"),
                "cost_bps": man.get("cost_bps"),
                "control": man.get("control"),
                "data_source": man.get("data_source"),
                "created_at_utc": man.get("created_at_utc"),
                "code_commit": prov.get("code_commit"),
                "code_dirty": prov.get("code_dirty"),
            })
        return out

    def run(self, run_id: str) -> dict[str, Any]:
        """run.json of one run (raises ValueError or RunError, see backtest.runs)."""
        return read_manifest(self.project.runs_dir, run_id)

    def table(self, run_id: str, name: str) -> pd.DataFrame:
        """One hash-checked table of a run."""
        return read_table(self.project.runs_dir, run_id, name)

    def summaries(self) -> list[dict[str, Any]]:
        """run.json of every stored summary, oldest first."""
        return [m for m in list_runs(self.project.runs_dir) if m["kind"] == "summary"]

    def latest_summary(self) -> dict[str, Any] | None:
        """The newest summary, or None if no summary is stored."""
        found = self.summaries()
        return found[-1] if found else None

    # Trials ---------------------------------------------------------------

    def trials(self) -> list[Trial]:
        """Every line of the trial log, oldest first."""
        return TrialLog(self.project.trials_path).read()

    def trial_stats(self) -> dict[str, Any]:
        """Counts over the trial log.

        Keys:
            n_lines: lines in the log.
            by_kind, by_label, by_outcome: counts (an unlock_event has no
                label and is counted under "none").
            n_backtests_counted: real-data backtests that count as attempts
                (backtest.runner.counts_for_deflation).
            n_screened_not_backtested: real candidates analysed and never
                backtested, each counted as one attempt.
            n_counted: the trial count the Deflated Sharpe ratio uses now,
                the sum of the two above.
            dirty_lines: 1-based line numbers whose code_dirty is true.
        """
        trials = self.trials()
        n_backtests = sum(counts_for_deflation(t) for t in trials)
        n_screened = len(screened_not_backtested(trials))
        return {
            "n_lines": len(trials),
            "by_kind": dict(Counter(t.kind for t in trials)),
            "by_label": dict(Counter(t.label or "none" for t in trials)),
            "by_outcome": dict(Counter(t.outcome for t in trials)),
            "n_backtests_counted": n_backtests,
            "n_screened_not_backtested": n_screened,
            "n_counted": n_backtests + n_screened,
            "dirty_lines": [i for i, t in enumerate(trials, start=1) if t.code_dirty],
        }

    # Configs and pairs ----------------------------------------------------

    def configs(self) -> list[dict[str, str]]:
        """Each config file with its path, SHA-256 and text."""
        out = []
        for name in CONFIG_NAMES:
            path = self.project.config_path(name)
            out.append({
                "name": name,
                "path": str(path.relative_to(self.project.root)),
                "sha256": file_sha256(path),
                "text": path.read_text(encoding="utf-8"),
            })
        return out

    def pairs(self) -> dict[str, Any]:
        """The demo pairs, basket and synthetic pair, each with its screen status.

        The status is the latest formation-period analysis in the trial log
        (backtest.runner.screen_status), the same one the backtests show.
        """
        config = load_pairs(self.project.pairs_path)
        trials = self.trials()
        pairs = [
            {"a": p.a, "b": p.b, "label": p.label,
             "screen": screen_status(trials, (p.a, p.b))}
            for p in config.pairs
        ]
        synthetic = config.synthetic
        return {
            "pairs": pairs,
            "basket": {
                "tickers": list(config.basket),
                "screen": screen_status(trials, config.basket),
            },
            "synthetic": {
                "a": synthetic.name_a, "b": synthetic.name_b, "label": "synthetic",
                "seed": synthetic.seed, "beta": synthetic.beta,
                "half_life": synthetic.half_life,
                "screen": screen_status(trials, (synthetic.name_a, synthetic.name_b)),
            },
        }

    # Data provenance ------------------------------------------------------

    def snapshots(self) -> list[dict[str, Any]]:
        """Every snapshot in the manifest with its provenance, in manifest order.

        Each record has snapshot_id, source, key, retrieved_at_utc, first_date,
        last_date, n_rows, url, file_present (the file exists on this
        computer; a fresh clone has the manifest but no files) and
        downloaded_before_terms_check.
        """
        manifest = Manifest(self.project.data_dir / "manifest.json")
        raw_dir = self.project.data_dir / RAW_DIR
        out = []
        for entry in manifest.entries():
            path = self.project.data_dir / entry.path
            present = path.resolve().is_relative_to(raw_dir.resolve()) and path.is_file()
            out.append({
                "snapshot_id": entry.snapshot_id,
                "source": entry.source,
                "key": entry.key,
                "retrieved_at_utc": entry.retrieved_at_utc,
                "first_date": entry.first_date,
                "last_date": entry.last_date,
                "n_rows": entry.n_rows,
                "url": entry.url,
                "file_present": present,
                "downloaded_before_terms_check": downloaded_before_terms_check(entry),
            })
        return out

    def cached_tickers(self, source: str = SOURCE) -> list[str]:
        """Tickers whose latest snapshot from `source` is on this computer, sorted.

        These are the only tickers the dashboard can analyse while downloads
        are disabled.
        """
        latest: dict[str, dict[str, Any]] = {}
        for snap in self.snapshots():
            if snap["source"] != source:
                continue
            seen = latest.get(snap["key"])
            if seen is None or snap["retrieved_at_utc"] > seen["retrieved_at_utc"]:
                latest[snap["key"]] = snap
        return sorted(k for k, s in latest.items() if s["file_present"])

    def sources(self) -> list[SourceInfo]:
        """The data sources the project knows, with their download switch."""
        return list(SOURCES.values())

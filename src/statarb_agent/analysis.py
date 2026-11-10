"""Analyse one pair end to end and write it to the trial log.

This is the path behind `statarb analyse` and `statarb demo`. For a real pair:

1. Make sure both tickers and the reference calendar ticker are cached
   (download them unless `offline`; every download is reported).
2. Load each from its snapshot with the as-of date of the period. The price
   source cuts at asof before anything else, so later rows are never read.
3. Run the data checks on each leg against the reference trading days. A
   fatal check refuses the analysis. Anomaly flags are recorded, never fixed.
4. Align the two legs explicitly; a date mismatch refuses the analysis.
5. Compute the statistics on log total-return prices (stats.pair.pair_stats)
   and apply the screen (screen.apply_screen).
6. Append one line to the trial log, whatever the outcome.

Nothing here computes a statistic; it only calls tested code in order.

Signals use `tr_close`, the forward-accumulated total-return index, so
dividends are included without reading any later row.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from statarb_agent.data.alignment import AlignmentError, AlignmentReport, align_pair
from statarb_agent.data.checks import DataCheck, check_history, fatal_failures, flags
from statarb_agent.data.synthetic import simulate_cointegrated_pair
from statarb_agent.project import (
    DataConfig,
    PairsConfig,
    Project,
    SyntheticSpec,
    load_data_config,
    load_pairs,
)
from statarb_agent.provenance import code_version
from statarb_agent.screen import ScreenConfig, ScreenResult, apply_screen, load_screen
from statarb_agent.sources.base import NotCachedError, SnapshotStore
from statarb_agent.sources.prices import (
    SOURCE,
    DownloadError,
    PriceRequest,
    YFinancePrices,
)
from statarb_agent.sources.tickers import normalise_ticker
from statarb_agent.stats.pair import PairStats, pair_stats
from statarb_agent.study import (
    TEST_START,
    Period,
    StudyConfig,
    load_study,
)
from statarb_agent.trials import TrialLog, record_unlock_event, unlock_record

SURVIVORSHIP_NOTE = (
    "Free data covers only tickers that still trade, so results have "
    "survivorship bias."
)


class OfflineError(RuntimeError):
    """A download was needed but `offline` forbids downloads."""


@dataclass(frozen=True)
class PairAnalysis:
    """Everything one analysis produced.

    Attributes:
        label: case_study, exploratory, control or synthetic.
        ticker_a, ticker_b: The legs.
        period_name, start, asof: The window; rows are in [start, asof).
        outcome: "ok", "refused" (a data rule stopped it) or "error".
        reason: Why it was refused or failed, or None.
        data_source: "yfinance" or "synthetic".
        snapshot_ids: Snapshot used for each ticker (empty for synthetic).
        downloaded: Tickers downloaded during this call.
        checks: Data checks per leg (empty for synthetic).
        alignment: Alignment report, or None if not reached.
        stats: Pair statistics, or None if not reached.
        screen: Screen result, or None if not reached.
        trial_id: Id of the trial-log line written for this analysis.
    """

    label: str
    ticker_a: str
    ticker_b: str
    period_name: str
    start: str
    asof: str
    outcome: str
    reason: str | None
    data_source: str
    snapshot_ids: dict[str, str] = field(default_factory=dict)
    downloaded: tuple[str, ...] = ()
    checks: dict[str, tuple[DataCheck, ...]] = field(default_factory=dict)
    alignment: AlignmentReport | None = None
    stats: PairStats | None = None
    screen: ScreenResult | None = None
    trial_id: str | None = None

    def flags(self) -> list[DataCheck]:
        """Anomaly flags that fired on either leg."""
        return [c for checks in self.checks.values() for c in flags(list(checks))]

    def result_dict(self) -> dict[str, Any]:
        """The analysis itself: what depends only on rows in [start, asof).

        It leaves out everything that names a run or a snapshot (trial id,
        snapshot ids, downloads), so two runs on data that agree before asof
        give equal dicts. The end-to-end look-ahead test compares this.
        """
        return {
            "label": self.label,
            "tickers": [self.ticker_a, self.ticker_b],
            "period": {"name": self.period_name, "start": self.start, "asof": self.asof},
            "outcome": self.outcome,
            "reason": self.reason,
            "data_source": self.data_source,
            "checks": {
                ticker: [dataclasses.asdict(c) for c in checks]
                for ticker, checks in self.checks.items()
            },
            "alignment": (
                None if self.alignment is None else dataclasses.asdict(self.alignment)
            ),
            "stats": None if self.stats is None else self.stats.to_dict(),
            "screen": None if self.screen is None else self.screen.to_dict(),
        }

    def to_dict(self) -> dict[str, Any]:
        """result_dict plus the run record (trial id, snapshots, downloads)."""
        return {
            "result": self.result_dict(),
            "record": {
                "trial_id": self.trial_id,
                "snapshot_ids": dict(self.snapshot_ids),
                "downloaded": list(self.downloaded),
                "survivorship_bias": self.data_source == SOURCE,
            },
        }


class Analyser:
    """Runs analyses for one project: configs, price source and trial log."""

    def __init__(
        self,
        project: Project,
        *,
        source: YFinancePrices | None = None,
        log: TrialLog | None = None,
    ) -> None:
        self.project = project
        self.study: StudyConfig = load_study(project.study_path)
        self.screen: ScreenConfig = load_screen(project.screen_path)
        self.data: DataConfig = load_data_config(project.data_config_path)
        self.pairs: PairsConfig = load_pairs(project.pairs_path)
        self.source = source or YFinancePrices(
            SnapshotStore(project.data_dir, repo_root=project.root),
            study=self.study,
            pause_s=self.data.pause_seconds,
        )
        self.log = log or TrialLog(project.trials_path)

    # Caching ---------------------------------------------------------------

    def is_cached(self, ticker: str) -> bool:
        """True if the latest snapshot of `ticker` is listed and its file exists."""
        try:
            entry = self.source.entry_for(ticker)
        except NotCachedError:
            return False
        return (self.source.store.root / entry.path).is_file()

    def fetch(self, ticker: str) -> str:
        """Download one ticker from download_start to the lock date.

        Returns the new snapshot id. The end date requested is TEST_START; the
        price source clips any later end to it while the test period is locked.
        """
        entry = self.source.fetch(
            PriceRequest(ticker, self.data.download_start, str(TEST_START.date()))
        )
        return entry.snapshot_id

    def ensure_cached(self, tickers: list[str], *, offline: bool) -> list[str]:
        """Download each ticker that has no usable snapshot. Returns those fetched.

        Raises:
            OfflineError: If a download is needed and `offline` is True.
            DownloadError: If the source returns nothing for a ticker.
        """
        missing = [t for t in dict.fromkeys(tickers) if not self.is_cached(t)]
        if missing and offline:
            raise OfflineError(
                f"No cached data for {', '.join(missing)} and --offline forbids "
                f"downloads. Run `statarb fetch {' '.join(missing)}` first."
            )
        for i, ticker in enumerate(missing):
            if i:
                self.source.sleep(self.source.pause_s)
            self.fetch(ticker)
        return missing

    # Provenance ------------------------------------------------------------

    def _provenance(self) -> dict[str, Any]:
        version = code_version(self.project.root)
        hashes = self.project.config_hashes()
        record_unlock_event(
            self.log, self.study, self.project.root, config_hashes=hashes,
            code_commit=version.commit, code_dirty=version.dirty,
        )
        return {
            "config_hashes": hashes,
            "code_commit": version.commit,
            "code_dirty": version.dirty,
            "unlock": unlock_record(self.study, self.project.root),
        }

    def _record(self, analysis: PairAnalysis, parameters: dict[str, Any]) -> PairAnalysis:
        provenance = self._provenance()
        asof = pd.Timestamp(analysis.asof)
        trial = self.log.record(
            kind="pair_analysis",
            label=analysis.label,
            tickers=(analysis.ticker_a, analysis.ticker_b),
            period={
                "name": analysis.period_name, "start": analysis.start,
                "asof": analysis.asof,
            },
            data_source=analysis.data_source,
            survivorship_bias=analysis.data_source == SOURCE,
            snapshot_ids=analysis.snapshot_ids,
            test_period_touched=bool(
                analysis.data_source == SOURCE and asof > TEST_START
            ),
            outcome=analysis.outcome,
            reason=analysis.reason,
            parameters=parameters,
            results={
                "stats": None if analysis.stats is None else analysis.stats.to_dict(),
                "screen": None if analysis.screen is None else analysis.screen.to_dict(),
                "flags": [dataclasses.asdict(c) for c in analysis.flags()],
                "alignment": (
                    None if analysis.alignment is None
                    else dataclasses.asdict(analysis.alignment)
                ),
            },
            **provenance,
        )
        return dataclasses.replace(analysis, trial_id=trial.trial_id)

    # Analyses --------------------------------------------------------------

    def analyse_pair(
        self,
        ticker_a: str,
        ticker_b: str,
        *,
        period_name: str = "formation",
        label: str | None = None,
        offline: bool = False,
    ) -> PairAnalysis:
        """Analyse two real tickers on one study period and log the trial.

        Args:
            ticker_a, ticker_b: Any two different US tickers.
            period_name: "formation" or "validation" (from configs/study.yaml).
            label: Override the label; by default a demo pair gets its label
                from configs/pairs.yaml and anything else is exploratory.
            offline: If True, never download.

        Returns:
            A PairAnalysis. A refusal (data check, alignment, no data) is a
            normal return with outcome "refused", and is logged.

        Raises:
            ValueError: On an invalid ticker or the same ticker twice. Nothing
                is logged, because no analysis was attempted.
            OfflineError: If data is missing and `offline` is True.
            LockedPeriodError: If the period reaches into the locked test
                period.
        """
        a, b = normalise_ticker(ticker_a), normalise_ticker(ticker_b)
        if a == b:
            raise ValueError(f"a pair needs two different tickers, got {a} twice")
        period = self._period(period_name)
        base = PairAnalysis(
            label=label or self.pairs.label_for(a, b),
            ticker_a=a,
            ticker_b=b,
            period_name=period_name,
            start=str(period.start.date()),
            asof=str(period.asof.date()),
            outcome="ok",
            reason=None,
            data_source=SOURCE,
        )
        parameters = {"price": "log tr_close", "offline": offline}
        calendar_ticker = self.data.reference_calendar
        downloaded: list[str] = []
        try:
            downloaded = self.ensure_cached([a, b, calendar_ticker], offline=offline)
        except DownloadError as exc:
            return self._record(
                dataclasses.replace(base, outcome="refused", reason=str(exc)), parameters
            )
        base = dataclasses.replace(base, downloaded=tuple(downloaded))

        frames: dict[str, pd.DataFrame] = {}
        snapshot_ids: dict[str, str] = {}
        for ticker in dict.fromkeys([a, b, calendar_ticker]):
            try:
                frame = self.source.load(ticker, asof=period.asof, start=period.start)
            except ValueError as exc:
                return self._record(
                    dataclasses.replace(
                        base, outcome="refused", snapshot_ids=snapshot_ids,
                        reason=f"{ticker} has no usable rows in the window: {exc}",
                    ),
                    parameters,
                )
            frames[ticker] = frame
            snapshot_ids[ticker] = frame.attrs["snapshot_id"]
        base = dataclasses.replace(base, snapshot_ids=snapshot_ids)

        calendar = pd.DatetimeIndex(frames[calendar_ticker].index)
        checks = {
            ticker: tuple(
                check_history(
                    frames[ticker],
                    ticker=ticker,
                    start=period.start,
                    asof=period.asof,
                    calendar=calendar,
                    min_obs=self.data.min_obs,
                    max_abs_log_return=self.data.max_abs_log_return,
                    max_distribution_fraction=self.data.max_distribution_fraction,
                    stale_run=self.data.stale_run,
                )
            )
            for ticker in (a, b)
        }
        base = dataclasses.replace(base, checks=checks)
        fatal = [c for ticker in (a, b) for c in fatal_failures(list(checks[ticker]))]
        if fatal:
            reason = "Data checks failed: " + "; ".join(c.detail for c in fatal)
            return self._record(
                dataclasses.replace(base, outcome="refused", reason=reason), parameters
            )

        log_a = np.log(frames[a]["tr_close"]).rename(a)
        log_b = np.log(frames[b]["tr_close"]).rename(b)
        try:
            log_a, log_b, alignment = align_pair(
                log_a, log_b, asof=period.asof, start=period.start,
                max_unmatched_days=self.data.max_unmatched_days,
                label_a=a, label_b=b,
            )
        except AlignmentError as exc:
            return self._record(
                dataclasses.replace(
                    base, outcome="refused", reason=str(exc), alignment=exc.report
                ),
                parameters,
            )
        base = dataclasses.replace(base, alignment=alignment)
        return self._finish(base, log_a, log_b, period, parameters)

    def analyse_synthetic(self, spec: SyntheticSpec | None = None) -> PairAnalysis:
        """Analyse the simulated demo pair with the same statistics and screen.

        The pair is simulated on business days from the formation start; all of
        its rows fall before the formation as-of date. It uses no downloaded
        data, so it has no snapshot ids and no survivorship bias.
        """
        spec = spec or self.pairs.synthetic
        period = self.study.formation
        frame = simulate_cointegrated_pair(
            seed=spec.seed, beta=spec.beta, alpha=spec.alpha,
            half_life=spec.half_life, spread_sd=spec.spread_sd,
            sigma_b=spec.sigma_b, n_obs=spec.n_obs,
            start=str(period.start.date()),
        )
        base = PairAnalysis(
            label="synthetic",
            ticker_a=spec.name_a,
            ticker_b=spec.name_b,
            period_name="formation",
            start=str(period.start.date()),
            asof=str(period.asof.date()),
            outcome="ok",
            reason=None,
            data_source="synthetic",
        )
        parameters = {"price": "simulated log price", **dataclasses.asdict(spec)}
        return self._finish(
            base, frame["log_a"].rename(spec.name_a), frame["log_b"].rename(spec.name_b),
            period, parameters,
        )

    def _finish(
        self,
        base: PairAnalysis,
        log_a: pd.Series,
        log_b: pd.Series,
        period: Period,
        parameters: dict[str, Any],
    ) -> PairAnalysis:
        try:
            stats = pair_stats(
                log_a, log_b, period.asof, start=period.start,
                label_a=base.ticker_a, label_b=base.ticker_b,
            )
        except ValueError as exc:
            return self._record(
                dataclasses.replace(
                    base, outcome="error", reason=f"statistics failed: {exc}"
                ),
                parameters,
            )
        result = apply_screen(stats, self.screen)
        return self._record(
            dataclasses.replace(base, stats=stats, screen=result), parameters
        )

    def _period(self, name: str) -> Period:
        if name == "formation":
            return self.study.formation
        if name == "validation":
            return self.study.validation
        raise ValueError(f"unknown period {name!r}; use formation or validation")

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

Steps 1 to 3 are `Analyser.load_checked`, which the backtest runner uses too,
so an analysis and a backtest of the same pair see the same checked data.

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
from statarb_agent.stats.johansen import JohansenResult, johansen_test
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


@dataclass(frozen=True)
class LoadedData:
    """Checked price data for some tickers on one window, or why it was refused.

    Attributes:
        tickers: The tickers asked for, normalised, in order.
        start, asof: The window; rows are in [start, asof).
        frames: Price frame per ticker (the price source's load output). Holds
            only the tickers loaded before a refusal.
        calendar_ticker: The reference calendar ticker (SPY).
        calendar_frame: Its price frame, or None if it was not loaded.
        snapshot_ids: Snapshot used per ticker, including the calendar ticker.
        downloaded: Tickers downloaded during this call.
        checks: Data checks per ticker.
        refusal: None if every ticker passed, else the reason to refuse.
    """

    tickers: tuple[str, ...]
    start: str
    asof: str
    frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    calendar_ticker: str = ""
    calendar_frame: pd.DataFrame | None = None
    snapshot_ids: dict[str, str] = field(default_factory=dict)
    downloaded: tuple[str, ...] = ()
    checks: dict[str, tuple[DataCheck, ...]] = field(default_factory=dict)
    refusal: str | None = None

    def flags(self) -> list[DataCheck]:
        """Anomaly flags that fired on any ticker."""
        return [c for checks in self.checks.values() for c in flags(list(checks))]


@dataclass(frozen=True)
class BasketAnalysis:
    """Johansen analysis of a basket on one study period.

    Attributes:
        tickers: The basket, in order.
        period_name, start, asof: The window.
        outcome, reason: "ok", or "refused" / "error" with the reason.
        snapshot_ids, downloaded, checks: As for PairAnalysis.
        johansen: The test result, or None if not reached.
        screen_passed: True if the trace test finds at least `min_rank`
            relations at 5 percent; None if not reached.
        min_rank: The rank required to pass.
        trial_id: Id of the trial-log line.
    """

    tickers: tuple[str, ...]
    period_name: str
    start: str
    asof: str
    outcome: str
    reason: str | None
    snapshot_ids: dict[str, str] = field(default_factory=dict)
    downloaded: tuple[str, ...] = ()
    checks: dict[str, tuple[DataCheck, ...]] = field(default_factory=dict)
    johansen: JohansenResult | None = None
    screen_passed: bool | None = None
    min_rank: int = 1
    trial_id: str | None = None


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
            DownloadsDisabledError: If a download is needed and the source's
                downloads are disabled (yfinance since 2026-11-23). Nothing is
                logged, because no request is made.
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

    def load_checked(
        self,
        tickers: list[str],
        *,
        start: pd.Timestamp,
        asof: pd.Timestamp,
        offline: bool,
    ) -> LoadedData:
        """Cache, load and check several tickers on the window [start, asof).

        Each ticker is loaded from its latest snapshot with `asof` (the price
        source cuts there before anything else) and checked against the
        reference calendar's trading days in the window. The first problem
        found is returned as `refusal`; nothing is raised for bad data.

        Raises:
            ValueError: On an invalid ticker or a ticker given twice.
            OfflineError: If a download is needed and `offline` is True.
            LockedPeriodError: If asof reaches into the locked test period.
        """
        names = [normalise_ticker(t) for t in tickers]
        if len(set(names)) != len(names):
            raise ValueError(f"a ticker is listed twice: {', '.join(names)}")
        calendar_ticker = self.data.reference_calendar
        loaded = LoadedData(
            tickers=tuple(names), start=str(start.date()), asof=str(asof.date()),
            calendar_ticker=calendar_ticker,
        )
        try:
            downloaded = self.ensure_cached([*names, calendar_ticker], offline=offline)
        except DownloadError as exc:
            return dataclasses.replace(loaded, refusal=str(exc))
        loaded = dataclasses.replace(loaded, downloaded=tuple(downloaded))

        frames: dict[str, pd.DataFrame] = {}
        snapshot_ids: dict[str, str] = {}
        for ticker in dict.fromkeys([*names, calendar_ticker]):
            try:
                frame = self.source.load(ticker, asof=asof, start=start)
            except ValueError as exc:
                return dataclasses.replace(
                    loaded,
                    frames={t: f for t, f in frames.items() if t in names},
                    snapshot_ids=snapshot_ids,
                    refusal=f"{ticker} has no usable rows in the window: {exc}",
                )
            frames[ticker] = frame
            snapshot_ids[ticker] = frame.attrs["snapshot_id"]
        calendar_frame = frames[calendar_ticker]
        calendar = pd.DatetimeIndex(calendar_frame.index)
        checks = {
            ticker: tuple(
                check_history(
                    frames[ticker],
                    ticker=ticker,
                    start=start,
                    asof=asof,
                    calendar=calendar,
                    min_obs=self.data.min_obs,
                    max_abs_log_return=self.data.max_abs_log_return,
                    max_distribution_fraction=self.data.max_distribution_fraction,
                    stale_run=self.data.stale_run,
                )
            )
            for ticker in names
        }
        loaded = dataclasses.replace(
            loaded,
            frames={t: frames[t] for t in names},
            calendar_frame=calendar_frame,
            snapshot_ids=snapshot_ids,
            checks=checks,
        )
        fatal = [c for ticker in names for c in fatal_failures(list(checks[ticker]))]
        if fatal:
            reason = "Data checks failed: " + "; ".join(c.detail for c in fatal)
            return dataclasses.replace(loaded, refusal=reason)
        return loaded

    # Provenance ------------------------------------------------------------

    def provenance(self) -> dict[str, Any]:
        """Config hashes, code version and unlock commits for a trial line.

        Also writes the unlock event to the trial log if the test period is
        unlocked and that event is not logged yet.
        """
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
        provenance = self.provenance()
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
        loaded = self.load_checked(
            [a, b], start=period.start, asof=period.asof, offline=offline
        )
        base = dataclasses.replace(
            base, downloaded=loaded.downloaded, snapshot_ids=loaded.snapshot_ids,
            checks=loaded.checks,
        )
        if loaded.refusal is not None:
            return self._record(
                dataclasses.replace(base, outcome="refused", reason=loaded.refusal),
                parameters,
            )
        frames = loaded.frames

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
        frame = simulate_cointegrated_pair(
            seed=spec.seed, beta=spec.beta, alpha=spec.alpha,
            half_life=spec.half_life, spread_sd=spec.spread_sd,
            sigma_b=spec.sigma_b, n_obs=spec.n_obs,
            start=str(self.study.formation.start.date()),
        )
        return self.analyse_simulated(
            frame["log_a"], frame["log_b"], name_a=spec.name_a, name_b=spec.name_b,
            parameters={"price": "simulated log price", **dataclasses.asdict(spec)},
        )

    def analyse_simulated(
        self,
        log_a: pd.Series,
        log_b: pd.Series,
        *,
        name_a: str,
        name_b: str,
        parameters: dict[str, Any],
    ) -> PairAnalysis:
        """Analyse any simulated pair on the formation period and log the trial.

        Only rows in the formation period are used; later rows of the series
        are never read. The trial is labelled synthetic.
        """
        period = self.study.formation
        base = PairAnalysis(
            label="synthetic",
            ticker_a=name_a,
            ticker_b=name_b,
            period_name="formation",
            start=str(period.start.date()),
            asof=str(period.asof.date()),
            outcome="ok",
            reason=None,
            data_source="synthetic",
        )
        return self._finish(
            base, log_a.rename(name_a), log_b.rename(name_b), period, parameters
        )

    def analyse_basket(
        self,
        tickers: list[str] | None = None,
        *,
        period_name: str = "formation",
        det_order: int = 0,
        k_ar_diff: int = 1,
        min_rank: int = 1,
        label: str = "case_study",
        offline: bool = False,
    ) -> BasketAnalysis:
        """Johansen test of a basket on one study period, logged as a trial.

        The basket passes its screen if the sequential trace test at 5 percent
        finds at least `min_rank` cointegrating relations.

        Args:
            tickers: The basket; default the one in configs/pairs.yaml.
            period_name: "formation" or "validation".
            det_order, k_ar_diff: Johansen settings.
            min_rank: Rank needed to pass.
            label: Trial label.
            offline: If True, never download.
        """
        names = [normalise_ticker(t) for t in (tickers or self.pairs.basket)]
        if len(names) < 3:
            raise ValueError("a basket needs at least three tickers")
        period = self._period(period_name)
        loaded = self.load_checked(
            names, start=period.start, asof=period.asof, offline=offline
        )
        base = BasketAnalysis(
            tickers=tuple(names),
            period_name=period_name,
            start=str(period.start.date()),
            asof=str(period.asof.date()),
            outcome="ok",
            reason=None,
            snapshot_ids=loaded.snapshot_ids,
            downloaded=loaded.downloaded,
            checks=loaded.checks,
            min_rank=min_rank,
        )
        result: JohansenResult | None = None
        if loaded.refusal is not None:
            base = dataclasses.replace(base, outcome="refused", reason=loaded.refusal)
        else:
            log_prices = pd.DataFrame(
                {t: np.log(loaded.frames[t]["tr_close"]) for t in names}
            )
            try:
                result = johansen_test(
                    log_prices, period.asof, det_order=det_order, k_ar_diff=k_ar_diff
                )
            except ValueError as exc:
                base = dataclasses.replace(
                    base, outcome="error", reason=f"statistics failed: {exc}"
                )
        if result is not None:
            base = dataclasses.replace(
                base, johansen=result, screen_passed=result.rank_trace >= min_rank
            )
        trial = self.log.record(
            kind="basket_analysis",
            label=label,
            tickers=tuple(names),
            period={"name": period_name, "start": base.start, "asof": base.asof},
            data_source=SOURCE,
            survivorship_bias=True,
            snapshot_ids=base.snapshot_ids,
            test_period_touched=bool(period.asof > TEST_START),
            outcome=base.outcome,
            reason=base.reason,
            parameters={
                "price": "log tr_close", "det_order": det_order,
                "k_ar_diff": k_ar_diff, "min_rank": min_rank, "offline": offline,
            },
            results={
                "johansen": None if result is None else dataclasses.asdict(result),
                "screen": (
                    None if result is None
                    else {
                        "passed": base.screen_passed,
                        "criteria": [
                            {
                                "name": "johansen_rank",
                                "passed": base.screen_passed,
                                "detail": (
                                    f"Johansen trace rank {result.rank_trace} at 5 "
                                    f"percent; at least {min_rank} required"
                                ),
                            }
                        ],
                    }
                ),
                "flags": [dataclasses.asdict(c) for c in loaded.flags()],
            },
            **self.provenance(),
        )
        return dataclasses.replace(base, trial_id=trial.trial_id)

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

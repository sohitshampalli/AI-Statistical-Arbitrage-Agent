"""Run backtests on project data, log every run as a trial, store the artifact.

This is the path behind `statarb backtest` and `statarb backtest-demo`. Each
run does the same things in the same order:

1. Load the legs through Analyser.load_checked (cached snapshots, cut at the
   as-of date, checked against the reference calendar). A failed check is a
   refusal, which is logged and stops the run.
2. Run the walk-forward engine on the formation and validation periods
   together (the as-of date is the start of the locked test period, so no
   test-period row exists in the data at all).
3. Compute the metrics of each span with backtest.summary.
4. Append one line to the trial log: every run is a trial, including each
   cost level and each hedge variant.
5. Compute the Deflated Sharpe ratio against every real-data backtest trial
   logged so far, this one included, and write the run folder.

The screen status shown next to a result is read from the trial log (the
pair's latest formation-period analysis). A backtest never re-runs an
analysis.

Which trials count for the Deflated Sharpe ratio: backtest trials with outcome
"ok" on downloaded data, except placebo and control batches. Simulated runs are
not attempts to find a real edge and are left out; the unrelated control pair
is real data and is counted.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from statarb_agent.analysis import Analyser, LoadedData
from statarb_agent.backtest import metrics as m
from statarb_agent.backtest.config import HEDGES, BacktestConfig, load_backtest_config
from statarb_agent.backtest.controls import (
    placebo_rank,
    run_batch,
    shuffle_pair,
    simulated_pair_frames,
    summarise_batch,
)
from statarb_agent.backtest.engine import (
    BacktestResult,
    run_basket_backtest,
    run_pair_backtest,
    run_settings,
)
from statarb_agent.backtest.runs import list_runs, read_manifest, read_table, write_run
from statarb_agent.backtest.summary import (
    simple_returns,
    study_span_metrics,
)
from statarb_agent.sources.prices import SOURCE
from statarb_agent.sources.tickers import normalise_ticker
from statarb_agent.trials import Trial, new_trial_id

SPANS = ("full", "formation", "validation")
PERIOD_NAME = "formation+validation"
SIMULATED_LABELS = {
    "cointegrated": ("SIM_A", "SIM_B"),
    "random_walk": ("RW_A", "RW_B"),
}


@dataclass(frozen=True)
class RunRecord:
    """What one run produced.

    Attributes:
        run_id: The run's id, which is also its trial id.
        kind: "backtest", "control_batch" or "summary".
        outcome: "ok", "refused" or "error".
        reason: Why it was refused or failed, or None.
        manifest: Contents of run.json (empty if no artifact was written).
        path: The run folder, or None if no artifact was written.
    """

    run_id: str
    kind: str
    outcome: str
    reason: str | None
    manifest: dict[str, Any]
    path: Path | None


def screen_status(trials: list[Trial], tickers: tuple[str, ...]) -> dict[str, Any]:
    """Screen result of the latest formation-period analysis of these tickers.

    Looks for the newest pair_analysis or basket_analysis trial on the
    formation period with the same tickers in any order. Returns a dict with
    status ("pass", "fail", "refused", "error" or "not_analysed"), the trial
    id it came from, and the criteria.
    """
    wanted = set(tickers)
    for trial in reversed(trials):
        if trial.kind not in ("pair_analysis", "basket_analysis"):
            continue
        if set(trial.tickers) != wanted or trial.period.get("name") != "formation":
            continue
        if trial.outcome != "ok":
            return {"status": trial.outcome, "trial_id": trial.trial_id,
                    "criteria": [], "reason": trial.reason}
        screen = trial.results.get("screen") or {}
        return {
            "status": "pass" if screen.get("passed") else "fail",
            "trial_id": trial.trial_id,
            "criteria": screen.get("criteria", []),
            "reason": None,
        }
    return {"status": "not_analysed", "trial_id": None, "criteria": [], "reason": None}


def counts_for_deflation(trial: Trial) -> bool:
    """True if a trial is a real-data backtest that counts as an attempt."""
    return (
        trial.kind == "backtest"
        and trial.outcome == "ok"
        and trial.data_source == SOURCE
        and trial.parameters.get("placebo") is None
        and trial.parameters.get("batch") is None
    )


def trial_sharpes(trials: list[Trial], span: str) -> np.ndarray:
    """Per-period Sharpe ratio of every counted trial on one span (NaN if none)."""
    values = []
    for trial in trials:
        if not counts_for_deflation(trial):
            continue
        metrics = (trial.results.get("metrics") or {}).get(span) or {}
        value = metrics.get("sharpe_per_period")
        values.append(float("nan") if value is None else float(value))
    return np.array(values, dtype=float)


def deflated_sharpes(
    spans: dict[str, dict[str, Any] | None], trials: list[Trial]
) -> dict[str, dict[str, Any] | None]:
    """Deflated Sharpe ratio of one run on each span, given the trial log.

    For each span the run's per-period Sharpe ratio is judged against the
    Sharpe ratios of all counted trials on the same span.
    """
    out: dict[str, dict[str, Any] | None] = {}
    for span, metrics in spans.items():
        if metrics is None:
            out[span] = None
            continue
        value = metrics["sharpe_per_period"]
        result = m.deflated_sharpe_ratio(
            float("nan") if value is None else float(value),
            int(metrics["n_days"]),
            _nan(metrics["skewness"]),
            _nan(metrics["kurtosis"]),
            trial_sharpes(trials, span),
        )
        out[span] = dataclasses.asdict(result)
    return out


def _nan(value: Any) -> float:
    return float("nan") if value is None else float(value)


class Backtester:
    """Runs and records backtests for one project."""

    def __init__(self, analyser: Analyser, config: BacktestConfig | None = None) -> None:
        self.analyser = analyser
        self.project = analyser.project
        self.study = analyser.study
        self.log = analyser.log
        self.config = config or load_backtest_config(self.project.backtest_path)
        self.start = self.study.formation.start
        self.asof = self.study.validation.asof

    # Shared pieces ---------------------------------------------------------

    def _period(self) -> dict[str, str]:
        return {
            "name": PERIOD_NAME,
            "start": str(self.start.date()),
            "asof": str(self.asof.date()),
        }

    def _record_trial(
        self,
        *,
        label: str,
        tickers: tuple[str, ...],
        data_source: str,
        snapshot_ids: dict[str, str],
        outcome: str,
        reason: str | None,
        parameters: dict[str, Any],
        results: dict[str, Any],
    ) -> Trial:
        return self.log.record(
            kind="backtest",
            label=label,
            tickers=tickers,
            period=self._period(),
            data_source=data_source,
            survivorship_bias=data_source == SOURCE,
            snapshot_ids=snapshot_ids,
            test_period_touched=False,
            outcome=outcome,
            reason=reason,
            parameters=parameters,
            results=results,
            **self.analyser.provenance(),
        )

    def _manifest(self, trial: Trial, extra: dict[str, Any]) -> dict[str, Any]:
        return {
            "created_at_utc": trial.recorded_at_utc,
            "label": trial.label,
            "tickers": list(trial.tickers),
            "data_source": trial.data_source,
            "survivorship_bias": trial.survivorship_bias,
            "period": trial.period,
            "provenance": {
                "trial_id": trial.trial_id,
                "code_commit": trial.code_commit,
                "code_dirty": trial.code_dirty,
                "config_hashes": trial.config_hashes,
                "snapshot_ids": trial.snapshot_ids,
            },
            **extra,
        }

    def _store(
        self, run_id: str, kind: str, manifest: dict[str, Any],
        tables: dict[str, pd.DataFrame],
    ) -> RunRecord:
        """Write the run folder and return the record with the stored manifest.

        The manifest is read back from disk, so what the caller gets is exactly
        what the dashboard will read (an undefined number is null, and the
        file list is included).
        """
        path = write_run(self.project.runs_dir, run_id, manifest, tables)
        stored = read_manifest(self.project.runs_dir, run_id)
        return RunRecord(run_id, kind, "ok", None, stored, path)

    def _refused(
        self,
        *,
        label: str,
        tickers: tuple[str, ...],
        loaded: LoadedData,
        parameters: dict[str, Any],
        outcome: str,
        reason: str,
    ) -> RunRecord:
        trial = self._record_trial(
            label=label, tickers=tickers, data_source=SOURCE,
            snapshot_ids=loaded.snapshot_ids, outcome=outcome, reason=reason,
            parameters=parameters,
            results={"flags": [dataclasses.asdict(c) for c in loaded.flags()]},
        )
        return RunRecord(trial.trial_id, "backtest", outcome, reason, {}, None)

    def _load(self, tickers: list[str], offline: bool) -> LoadedData:
        loaded = self.analyser.load_checked(
            tickers, start=self.start, asof=self.asof, offline=offline
        )
        if loaded.refusal is None:
            calendar = loaded.calendar_frame.index
            for ticker, frame in loaded.frames.items():
                if not frame.index.equals(calendar):
                    return dataclasses.replace(
                        loaded,
                        refusal=f"{ticker} does not have exactly the reference "
                        "calendar's trading days",
                    )
        return loaded

    def _finish_run(
        self,
        result: BacktestResult,
        *,
        label: str,
        data_source: str,
        snapshot_ids: dict[str, str],
        benchmark: pd.Series | None,
        prices: pd.DataFrame,
        flags: list[dict[str, Any]],
        downloaded: tuple[str, ...],
        extra_parameters: dict[str, Any],
    ) -> RunRecord:
        """Metrics, trial line, Deflated Sharpe and artifact for one engine result."""
        spans = study_span_metrics(result, self.study, benchmark=benchmark)
        screen = screen_status(self.log.read(), result.labels)
        closed = result.trades.loc[~result.trades["open"]]
        parameters = {
            **result.settings, "placebo": None, "batch": None, **extra_parameters,
        }
        trial = self._record_trial(
            label=label, tickers=result.labels, data_source=data_source,
            snapshot_ids=snapshot_ids, outcome="ok", reason=None,
            parameters=parameters,
            results={
                "metrics": spans,
                "screen_status": screen["status"],
                "screen_trial_id": screen["trial_id"],
                "flags": flags,
                "n_windows": len(result.windows),
                "n_closed_trades": len(closed),
            },
        )
        deflated = (
            deflated_sharpes(spans, self.log.read()) if data_source == SOURCE else None
        )
        manifest = self._manifest(
            trial,
            {
                "kind": "backtest",
                "strategy": result.kind,
                "hedge": result.hedge,
                "cost_bps": result.cost_bps,
                "settings": parameters,
                "screen": screen,
                "flags": flags,
                "downloaded": list(downloaded),
                "first_signal_date": str(result.first_signal_date.date()),
                "metrics": spans,
                "deflated_sharpe": deflated,
                "n_windows": len(result.windows),
            },
        )
        return self._store(
            trial.trial_id, "backtest", manifest,
            {
                "daily": result.daily,
                "trades": result.trades,
                "signals": result.signals,
                "windows": result.windows,
                "prices": prices,
            },
        )

    @staticmethod
    def _prices(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Total-return price of each leg, for the price charts."""
        return pd.DataFrame({label: f["tr_close"] for label, f in frames.items()})

    # Real data -------------------------------------------------------------

    def backtest_pair(
        self,
        ticker_a: str,
        ticker_b: str,
        *,
        hedge: str | None = None,
        cost_bps: float | None = None,
        label: str | None = None,
        offline: bool = False,
        extra_parameters: dict[str, Any] | None = None,
    ) -> RunRecord:
        """Backtest two real tickers on the formation and validation periods.

        Raises:
            ValueError: On an invalid ticker, the same ticker twice or an
                unknown hedge. Nothing is logged in that case.
            OfflineError: If data is missing and `offline` is True.
        """
        a, b = normalise_ticker(ticker_a), normalise_ticker(ticker_b)
        if a == b:
            raise ValueError(f"a pair needs two different tickers, got {a} twice")
        hedge = hedge or self.config.hedge_default
        if hedge not in HEDGES:
            # Checked here so that a typo is rejected and not logged as a trial.
            raise ValueError(f"hedge must be one of {HEDGES}, got {hedge!r}")
        settings = run_settings(self.config, "pair", hedge, cost_bps)
        label = label or self.analyser.pairs.label_for(a, b)
        parameters = {
            **settings, "placebo": None, "batch": None, **(extra_parameters or {}),
        }
        loaded = self._load([a, b], offline)
        if loaded.refusal is not None:
            return self._refused(
                label=label, tickers=(a, b), loaded=loaded, parameters=parameters,
                outcome="refused", reason=loaded.refusal,
            )
        try:
            result = run_pair_backtest(
                loaded.frames[a], loaded.frames[b], asof=self.asof, config=self.config,
                hedge=hedge, cost_bps=cost_bps, labels=(a, b),
            )
        except ValueError as exc:
            return self._refused(
                label=label, tickers=(a, b), loaded=loaded, parameters=parameters,
                outcome="error", reason=f"backtest failed: {exc}",
            )
        return self._finish_run(
            result, label=label, data_source=SOURCE, snapshot_ids=loaded.snapshot_ids,
            benchmark=simple_returns(loaded.calendar_frame["tr_close"]),
            prices=self._prices(loaded.frames),
            flags=[dataclasses.asdict(c) for c in loaded.flags()],
            downloaded=loaded.downloaded, extra_parameters=extra_parameters or {},
        )

    def backtest_basket(
        self,
        tickers: list[str] | None = None,
        *,
        cost_bps: float | None = None,
        label: str = "case_study",
        offline: bool = False,
        extra_parameters: dict[str, Any] | None = None,
    ) -> RunRecord:
        """Backtest a Johansen basket (default: the one in configs/pairs.yaml)."""
        names = [normalise_ticker(t) for t in (tickers or self.analyser.pairs.basket)]
        settings = run_settings(self.config, "basket", "johansen", cost_bps)
        parameters = {
            **settings, "placebo": None, "batch": None, **(extra_parameters or {}),
        }
        loaded = self._load(names, offline)
        if loaded.refusal is not None:
            return self._refused(
                label=label, tickers=tuple(names), loaded=loaded, parameters=parameters,
                outcome="refused", reason=loaded.refusal,
            )
        try:
            result = run_basket_backtest(
                {t: loaded.frames[t] for t in names}, asof=self.asof,
                config=self.config, cost_bps=cost_bps,
            )
        except ValueError as exc:
            return self._refused(
                label=label, tickers=tuple(names), loaded=loaded, parameters=parameters,
                outcome="error", reason=f"backtest failed: {exc}",
            )
        return self._finish_run(
            result, label=label, data_source=SOURCE, snapshot_ids=loaded.snapshot_ids,
            benchmark=simple_returns(loaded.calendar_frame["tr_close"]),
            prices=self._prices(loaded.frames),
            flags=[dataclasses.asdict(c) for c in loaded.flags()],
            downloaded=loaded.downloaded, extra_parameters=extra_parameters or {},
        )

    def placebo_batch(
        self,
        ticker_a: str,
        ticker_b: str,
        *,
        real: RunRecord,
        hedge: str | None = None,
        cost_bps: float | None = None,
        offline: bool = True,
    ) -> RunRecord:
        """Shuffled-date placebos of a real pair, logged as one trial.

        Both legs' dates are shuffled, once per seed, and each shuffled pair is
        backtested with the same settings as `real`. The result records where
        the real run's full-span net Sharpe ratio stands among the placebos.
        """
        a, b = normalise_ticker(ticker_a), normalise_ticker(ticker_b)
        hedge = hedge or self.config.hedge_default
        c = self.config.controls
        seeds = range(c.placebo_first_seed, c.placebo_first_seed + c.placebo_shuffles)
        parameters = {
            **run_settings(self.config, "pair", hedge, cost_bps),
            "placebo": {
                "first_seed": seeds.start, "shuffles": len(seeds), "legs": "both",
                "real_run_id": real.run_id,
            },
            "batch": None,
        }
        loaded = self._load([a, b], offline)
        if loaded.refusal is not None:
            return self._refused(
                label="control", tickers=(a, b), loaded=loaded, parameters=parameters,
                outcome="refused", reason=loaded.refusal,
            )
        batch = run_batch(
            lambda seed: shuffle_pair(loaded.frames[a], loaded.frames[b], seed),
            seeds, asof=self.asof, config=self.config, hedge=hedge, cost_bps=cost_bps,
        )
        summary = summarise_batch(batch)
        real_sharpe = _nan(((real.manifest.get("metrics") or {}).get("full") or {}).get("sharpe"))
        rank = placebo_rank(real_sharpe, batch["sharpe"].to_numpy(dtype=float))
        trial = self._record_trial(
            label="control", tickers=(a, b), data_source=SOURCE,
            snapshot_ids=loaded.snapshot_ids, outcome="ok", reason=None,
            parameters=parameters,
            results={"summary": summary, "real_sharpe": real_sharpe, "rank": rank},
        )
        manifest = self._manifest(
            trial,
            {
                "kind": "control_batch",
                "control": "placebo",
                "hedge": hedge,
                "cost_bps": parameters["cost_bps_per_leg"],
                "settings": parameters,
                "summary": summary,
                "real_run_id": real.run_id,
                "real_sharpe": real_sharpe,
                "rank": rank,
            },
        )
        return self._store(trial.trial_id, "control_batch", manifest, {"seeds": batch})

    # Simulated controls ----------------------------------------------------

    def _simulation_parameters(self, kind: str, seed: int | None) -> dict[str, Any]:
        c = self.config.controls
        out: dict[str, Any] = {"simulation": kind, "n_obs": c.n_obs, "sigma": c.sigma}
        if seed is not None:
            out["seed"] = seed
        if kind == "cointegrated":
            out.update(half_life=c.half_life, beta=c.beta, alpha=c.alpha,
                       spread_sd=c.spread_sd)
        return out

    def simulated_frames(self, kind: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Price frames of the single simulated control pair of this kind."""
        c = self.config.controls
        seed = c.synthetic_seed if kind == "cointegrated" else c.random_walk_seed
        return simulated_pair_frames(kind, seed, self.config, str(self.start.date()))

    def analyse_simulated(self, kind: str) -> None:
        """Log the formation-period analysis of a simulated control pair, once.

        Skipped if the trial log already holds one for these names, so that
        running the controls again does not add analysis trials.
        """
        labels = SIMULATED_LABELS[kind]
        if screen_status(self.log.read(), labels)["status"] != "not_analysed":
            return
        c = self.config.controls
        seed = c.synthetic_seed if kind == "cointegrated" else c.random_walk_seed
        a, b = self.simulated_frames(kind)
        self.analyser.analyse_simulated(
            np.log(a["tr_close"]), np.log(b["tr_close"]), name_a=labels[0],
            name_b=labels[1],
            parameters={"price": "simulated log price",
                        **self._simulation_parameters(kind, seed)},
        )

    def backtest_simulated(
        self,
        kind: str,
        *,
        hedge: str | None = None,
        cost_bps: float | None = None,
        extra_parameters: dict[str, Any] | None = None,
    ) -> RunRecord:
        """Backtest the single simulated control pair ("cointegrated" or "random_walk")."""
        labels = SIMULATED_LABELS[kind]
        c = self.config.controls
        seed = c.synthetic_seed if kind == "cointegrated" else c.random_walk_seed
        a, b = self.simulated_frames(kind)
        result = run_pair_backtest(
            a, b, asof=self.asof, config=self.config, hedge=hedge, cost_bps=cost_bps,
            labels=labels,
        )
        return self._finish_run(
            result, label="synthetic", data_source="synthetic", snapshot_ids={},
            benchmark=None, prices=self._prices({labels[0]: a, labels[1]: b}),
            flags=[], downloaded=(),
            extra_parameters={
                **self._simulation_parameters(kind, seed), **(extra_parameters or {}),
            },
        )

    def control_batch(
        self, kind: str, *, hedge: str | None = None, cost_bps: float | None = None
    ) -> RunRecord:
        """Backtest a batch of simulated pairs over fixed seeds, as one trial."""
        hedge = hedge or self.config.hedge_default
        c = self.config.controls
        seeds = range(c.batch_first_seed, c.batch_first_seed + c.batch_size)
        start = str(self.start.date())
        batch = run_batch(
            lambda seed: simulated_pair_frames(kind, seed, self.config, start),
            seeds, asof=self.asof, config=self.config, hedge=hedge, cost_bps=cost_bps,
        )
        summary = summarise_batch(batch)
        parameters = {
            **run_settings(self.config, "pair", hedge, cost_bps),
            "placebo": None,
            "batch": {"kind": kind, "first_seed": seeds.start, "size": len(seeds)},
            **self._simulation_parameters(kind, None),
        }
        trial = self._record_trial(
            label="synthetic", tickers=(f"{kind}_batch",), data_source="synthetic",
            snapshot_ids={}, outcome="ok", reason=None, parameters=parameters,
            results={"summary": summary},
        )
        manifest = self._manifest(
            trial,
            {
                "kind": "control_batch",
                "control": kind,
                "hedge": hedge,
                "cost_bps": parameters["cost_bps_per_leg"],
                "settings": parameters,
                "summary": summary,
            },
        )
        return self._store(trial.trial_id, "control_batch", manifest, {"seeds": batch})

    # Everything at once ----------------------------------------------------

    def demo_already_run(self) -> bool:
        """True if the trial log holds a demo backtest made with this config file."""
        current = self.project.config_hashes(("backtest",))["backtest"]
        return any(
            t.kind == "backtest" and t.parameters.get("demo") is True
            and t.config_hashes.get("backtest") == current
            for t in self.log.read()
        )

    def run_demo(self, *, offline: bool = False) -> list[RunRecord]:
        """Every pre-stated backtest: all demo pairs, the basket and the controls.

        - each demo pair (case studies and the unrelated control), each hedge
          variant, each cost level;
        - the Johansen basket at each cost level (its formation-period Johansen
          analysis is logged first if the log has none);
        - the simulated cointegrated pair and the simulated random-walk pair,
          each hedge variant and cost level (their formation-period analyses
          are logged first if missing);
        - batches of simulated cointegrated and random-walk pairs, each hedge
          variant, at the default cost;
        - shuffled-date placebos of each demo pair, default hedge and cost.

        Every run is a trial. Run this once: running it again logs every trial
        again, which the Deflated Sharpe ratio then counts.
        """
        cfg = self.config
        demo = {"demo": True}
        records: list[RunRecord] = []
        real_default: dict[tuple[str, str], RunRecord] = {}
        for pair in self.analyser.pairs.pairs:
            for hedge in cfg.hedge_variants:
                for cost in cfg.cost_sensitivity_bps:
                    record = self.backtest_pair(
                        pair.a, pair.b, hedge=hedge, cost_bps=cost, label=pair.label,
                        offline=offline, extra_parameters=demo,
                    )
                    records.append(record)
                    if hedge == cfg.hedge_default and cost == cfg.cost_bps_per_leg:
                        real_default[(pair.a, pair.b)] = record
        basket = tuple(self.analyser.pairs.basket)
        if screen_status(self.log.read(), basket)["status"] == "not_analysed":
            self.analyser.analyse_basket(
                det_order=cfg.basket_det_order, k_ar_diff=cfg.basket_k_ar_diff,
                offline=offline,
            )
        for cost in cfg.cost_sensitivity_bps:
            records.append(
                self.backtest_basket(cost_bps=cost, offline=offline, extra_parameters=demo)
            )
        for kind in ("cointegrated", "random_walk"):
            self.analyse_simulated(kind)
            for hedge in cfg.hedge_variants:
                for cost in cfg.cost_sensitivity_bps:
                    records.append(
                        self.backtest_simulated(
                            kind, hedge=hedge, cost_bps=cost, extra_parameters=demo
                        )
                    )
        for kind in ("cointegrated", "random_walk"):
            for hedge in cfg.hedge_variants:
                records.append(self.control_batch(kind, hedge=hedge))
        for (a, b), real in real_default.items():
            if real.outcome == "ok":
                records.append(self.placebo_batch(a, b, real=real, offline=True))
        return records

    # Summary ---------------------------------------------------------------

    def summarise(self) -> RunRecord:
        """Write a summary artifact of every stored backtest run.

        The summary reads only run folders and the trial log; it runs no
        backtest and is not a trial. For each real-data run it recomputes the
        Deflated Sharpe ratio against all counted trials in the log now, so
        every row uses the same, final trial count. The headline is the set of
        real pairs that passed the formation screen, at the default hedge and
        cost: the strategy as it was stated in advance.
        """
        trials = self.log.read()
        rows: list[dict[str, Any]] = []
        for manifest in list_runs(self.project.runs_dir):
            if manifest["kind"] != "backtest":
                continue
            real = manifest["data_source"] == SOURCE
            rows.append(
                {
                    "run_id": manifest["run_id"],
                    "tickers": manifest["tickers"],
                    "label": manifest["label"],
                    "strategy": manifest["strategy"],
                    "hedge": manifest["hedge"],
                    "cost_bps": manifest["cost_bps"],
                    "data_source": manifest["data_source"],
                    "screen_status": screen_status(trials, tuple(manifest["tickers"]))[
                        "status"
                    ],
                    "metrics": manifest["metrics"],
                    "deflated_sharpe": (
                        deflated_sharpes(manifest["metrics"], trials) if real else None
                    ),
                }
            )
        cfg = self.config
        headline_rows = [
            r for r in rows
            if r["data_source"] == SOURCE and r["label"] in ("case_study", "exploratory")
            and r["screen_status"] == "pass"
            and r["cost_bps"] == cfg.cost_bps_per_leg
            and r["hedge"] in (cfg.hedge_default, "johansen")
        ]
        headline = self._headline(headline_rows)
        now = self.log.clock()
        run_id = new_trial_id(now)
        version = self.analyser.provenance()
        manifest = {
            "kind": "summary",
            "created_at_utc": now.isoformat(),
            "provenance": {
                "code_commit": version["code_commit"],
                "code_dirty": version["code_dirty"],
                "config_hashes": version["config_hashes"],
            },
            "n_trials_in_log": len(trials),
            "n_trials_counted": int(sum(counts_for_deflation(t) for t in trials)),
            "default_hedge": cfg.hedge_default,
            "default_cost_bps": cfg.cost_bps_per_leg,
            "rows": rows,
            "headline": headline,
        }
        return self._store(run_id, "summary", manifest, {})

    def _headline(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """Equal-weight portfolio of the screened runs, or an explicit empty result."""
        if not rows:
            return {
                "n_runs": 0,
                "run_ids": [],
                "metrics": None,
                "statement": (
                    "No real pair or basket passed the formation-period screen, so "
                    "the strategy as stated in advance takes no positions. There is "
                    "no headline return to report."
                ),
            }
        dailies = [read_table(self.project.runs_dir, r["run_id"], "daily") for r in rows]
        trades = [read_table(self.project.runs_dir, r["run_id"], "trades") for r in rows]
        portfolio = equal_weight_portfolio(dailies, trades, self.config.capital)
        first = max(pd.Timestamp(r["metrics"]["full"]["start"]) for r in rows)
        result = BacktestResult(
            kind="portfolio", labels=tuple("+".join(r["tickers"]) for r in rows),
            hedge="mixed", cost_bps=self.config.cost_bps_per_leg, daily=portfolio[0],
            trades=portfolio[1], signals=pd.DataFrame(), windows=pd.DataFrame(),
            first_signal_date=first, settings={"capital": self.config.capital},
        )
        return {
            "n_runs": len(rows),
            "run_ids": [r["run_id"] for r in rows],
            "metrics": study_span_metrics(result, self.study),
            "statement": (
                f"Equal-weight portfolio of the {len(rows)} screened runs at the "
                "default hedge and cost."
            ),
        }


def equal_weight_portfolio(
    dailies: list[pd.DataFrame], trades: list[pd.DataFrame], capital: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Combine runs into one portfolio with the capital split equally.

    Each run was sized on the full capital, so the portfolio's daily profit is
    the mean of the runs' daily profits. `position` is 1 on days when any run
    holds a position. Trades are pooled; each trade's profit is divided by the
    number of runs.

    Raises:
        ValueError: If there are no runs or their dates differ.
    """
    if not dailies:
        raise ValueError("need at least one run")
    index = dailies[0].index
    if any(not d.index.equals(index) for d in dailies):
        raise ValueError("the runs have different dates")
    n = len(dailies)
    columns = ("price_pnl", "dist_pnl", "borrow_cost", "trade_cost", "gross_pnl", "pnl",
               "traded_notional")
    daily = pd.DataFrame(
        {c: sum(d[c].to_numpy(dtype=float) for d in dailies) / n for c in columns},
        index=index,
    )
    daily["ret"] = daily["pnl"] / capital
    daily["gross_ret"] = daily["gross_pnl"] / capital
    daily["position"] = (
        np.column_stack([d["position"].to_numpy() for d in dailies]) != 0
    ).any(axis=1).astype(np.int8)
    pooled = pd.concat(trades, ignore_index=True)
    for column in ("price_pnl", "dist_pnl", "borrow_cost", "trade_cost", "net_pnl"):
        pooled[column] = pooled[column] / n
    return daily, pooled


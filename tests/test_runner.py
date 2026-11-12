"""End-to-end tests of the backtest runner and its CLI, on the fake market.

Every test builds a throwaway project (configs copied from the repository, with
small control batches) and a fake downloader. Nothing touches the network, the
real data folder, the real trial log or the real reports folder.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fake_market import CALENDAR, FakeDownloader, base_frames, make_project
from typer.testing import CliRunner

from statarb_agent import cli
from statarb_agent.analysis import Analyser, OfflineError
from statarb_agent.backtest.engine import run_pair_backtest
from statarb_agent.backtest.runner import (
    Backtester,
    counts_for_deflation,
    equal_weight_portfolio,
    screen_status,
    screened_not_backtested,
    trial_sharpes,
)
from statarb_agent.backtest.runs import list_runs, read_manifest, read_table
from statarb_agent.project import Project
from statarb_agent.sources.base import SnapshotStore
from statarb_agent.sources.prices import YFinancePrices
from statarb_agent.study import LockedPeriodError, load_study
from statarb_agent.trials import TrialLog

N_ROWS = len(CALENDAR)


@pytest.fixture
def project(tmp_path: Path) -> Project:
    return make_project(tmp_path, small_controls=True)


@pytest.fixture
def downloader() -> FakeDownloader:
    return FakeDownloader(base_frames())


@pytest.fixture
def runner(project: Project, downloader: FakeDownloader) -> Backtester:
    study = load_study(project.study_path)
    source = YFinancePrices(
        SnapshotStore(project.data_dir, repo_root=project.root), study=study,
        downloader=downloader, pause_s=0.0,
    )
    analyser = Analyser(project, source=source, log=TrialLog(project.trials_path))
    return Backtester(analyser)


def test_pair_backtest_is_logged_and_stored(runner: Backtester) -> None:
    record = runner.backtest_pair("aaa", "bbb")
    assert record.outcome == "ok" and record.kind == "backtest"
    man = record.manifest
    assert man["tickers"] == ["AAA", "BBB"] and man["label"] == "exploratory"
    assert (man["hedge"], man["cost_bps"], man["strategy"]) == ("static", 10.0, "pair")
    assert man["period"] == {"name": "formation+validation", "start": "2010-01-01",
                             "asof": "2022-01-01"}
    assert man["survivorship_bias"] is True and man["data_source"] == "yfinance"
    assert man["downloaded"] == ["AAA", "BBB", "SPY"]
    assert man["screen"]["status"] == "not_analysed"
    assert set(man["metrics"]) == {"full", "formation", "validation"}
    assert man["metrics"]["formation"]["end"] == "2017-12-29"
    assert man["metrics"]["validation"]["start"] == "2018-01-01"
    assert man["metrics"]["validation"]["end"] == "2021-12-31"
    assert man["first_signal_date"] == str(CALENDAR[252].date())
    assert set(man["provenance"]["snapshot_ids"]) == {"AAA", "BBB", "SPY"}
    assert man["settings"]["time_stop_days"] == 30 and man["settings"]["placebo"] is None

    (trial,) = runner.log.read()
    assert trial.trial_id == record.run_id and trial.kind == "backtest"
    assert trial.parameters["hedge"] == "static" and trial.parameters["batch"] is None
    assert trial.results["metrics"]["full"]["n_days"] == N_ROWS - 252
    assert not trial.test_period_touched and trial.survivorship_bias
    assert trial.config_hashes["backtest"] == runner.project.config_hashes()["backtest"]

    # the stored tables are the engine's output on the checked data
    loaded = runner.analyser.load_checked(
        ["AAA", "BBB"], start=runner.start, asof=runner.asof, offline=True
    )
    direct = run_pair_backtest(
        loaded.frames["AAA"], loaded.frames["BBB"], asof=runner.asof,
        config=runner.config, labels=("AAA", "BBB"),
    )
    runs_dir = runner.project.runs_dir
    daily = read_table(runs_dir, record.run_id, "daily")
    pd.testing.assert_frame_equal(daily, direct.daily, check_freq=False)
    trades = read_table(runs_dir, record.run_id, "trades")
    assert len(trades) == len(direct.trades) > 0
    assert set(read_manifest(runs_dir, record.run_id)["files"]) == {
        "daily", "trades", "signals", "windows", "prices", "benchmark",
    }
    benchmark = read_table(runs_dir, record.run_id, "benchmark")
    spy = loaded.calendar_frame["tr_close"]
    assert benchmark["ret"].iloc[0] == pytest.approx(spy.iloc[1] / spy.iloc[0] - 1.0)
    assert man["spans_in_sample_for_screen"] == ["full", "formation"]
    open_trades = direct.trades.loc[direct.trades["open"]]
    assert man["open_at_end"]["open"] is bool(len(open_trades))
    assert man["open_at_end"]["exit_cost_not_charged_return"] == pytest.approx(
        direct.daily["gross_exposure"].iloc[-1] * 10e-4 / 1e6
    )
    prices = read_table(runs_dir, record.run_id, "prices")
    assert list(prices.columns) == ["AAA", "BBB"] and len(prices) == N_ROWS
    # one trial cannot be deflated: the ratio is stored as undefined (null)
    assert man["deflated_sharpe"]["validation"]["n_trials"] == 1
    assert man["deflated_sharpe"]["validation"]["dsr"] is None
    # the record carries exactly what is on disk
    assert man == read_manifest(runs_dir, record.run_id)


def test_screen_status_is_read_from_the_log_not_recomputed(runner: Backtester) -> None:
    analysis = runner.analyser.analyse_pair("AAA", "BBB")
    n_before = runner.log.count()
    record = runner.backtest_pair("BBB", "AAA")  # either order finds the analysis
    expected = "pass" if analysis.screen.passed else "fail"
    assert record.manifest["screen"]["status"] == expected
    assert record.manifest["screen"]["trial_id"] == analysis.trial_id
    assert runner.log.count() == n_before + 1  # the backtest only; no new analysis
    trials = runner.log.read()
    assert screen_status(trials, ("KO", "PEP"))["status"] == "not_analysed"
    refused = runner.analyser.analyse_pair("AAA", "GAP")
    status = screen_status(runner.log.read(), ("AAA", "GAP"))
    assert status["status"] == "refused" and status["trial_id"] == refused.trial_id


def test_cached_rows_at_or_after_asof_never_change_a_run(
    runner: Backtester, downloader: FakeDownloader
) -> None:
    """Look-ahead test through the runner: replace every snapshot by one that
    differs from the as-of date on, and require identical tables and metrics.

    The as-of date is moved to 2019-01-01 for this test so that the cache holds
    rows after it (with the real as-of date, 2022-01-01, no later row exists).
    """
    runner.asof = pd.Timestamp("2019-01-01")
    assert (CALENDAR.tz_localize(None) == runner.asof).any()
    before = runner.backtest_pair("AAA", "BBB", hedge="kalman")
    rng = np.random.default_rng(0)
    for ticker in ("AAA", "BBB", "SPY"):
        frame = downloader.frames[ticker].copy()
        later = frame.index.tz_localize(None) >= runner.asof
        n = int(later.sum())
        for column in ("Open", "High", "Low", "Close", "Adj Close"):
            frame.loc[later, column] = frame.loc[later, column].to_numpy() * rng.uniform(
                0.2, 5.0, n
            )
        frame.loc[later, "Dividends"] = rng.uniform(0.0, 20.0, n)
        position = int(np.argmax(later))
        frame.iloc[position + 3, frame.columns.get_loc("Close")] = np.nan
        downloader.frames[ticker] = frame.drop(frame.index[position + 10])
        runner.analyser.fetch(ticker)
    after = runner.backtest_pair("AAA", "BBB", hedge="kalman")
    assert after.manifest["provenance"]["snapshot_ids"] != (
        before.manifest["provenance"]["snapshot_ids"]
    )
    runs_dir = runner.project.runs_dir
    for table in ("daily", "trades", "signals", "windows", "prices"):
        pd.testing.assert_frame_equal(
            read_table(runs_dir, after.run_id, table),
            read_table(runs_dir, before.run_id, table),
        )
    assert json.dumps(after.manifest["metrics"], sort_keys=True) == json.dumps(
        before.manifest["metrics"], sort_keys=True
    )
    assert before.manifest["metrics"]["full"]["end"] == "2018-12-31"


def test_refusals_are_logged_without_an_artifact(runner: Backtester) -> None:
    record = runner.backtest_pair("AAA", "GAP")
    assert record.outcome == "refused" and record.path is None
    assert "GAP is missing 3 trading days" in record.reason
    (trial,) = runner.log.read()
    assert trial.kind == "backtest" and trial.outcome == "refused"
    assert not counts_for_deflation(trial)
    assert list_runs(runner.project.runs_dir) == []
    late = runner.backtest_pair("LATE", "BBB")
    assert late.outcome == "refused" and "LATE starts on" in late.reason
    with pytest.raises(ValueError, match="two different tickers"):
        runner.backtest_pair("AAA", "AAA")
    with pytest.raises(ValueError, match="hedge must be"):
        runner.backtest_pair("AAA", "BBB", hedge="magic")
    assert runner.log.count() == 2


def test_offline_never_downloads(runner: Backtester, downloader: FakeDownloader) -> None:
    with pytest.raises(OfflineError):
        runner.backtest_pair("AAA", "BBB", offline=True)
    assert downloader.calls == [] and runner.log.count() == 0


def test_each_cost_level_is_a_trial_and_feeds_the_deflated_sharpe(
    runner: Backtester,
) -> None:
    records = [runner.backtest_pair("AAA", "BBB", cost_bps=c) for c in (0.0, 10.0, 20.0)]
    trials = runner.log.read()
    assert [t.parameters["cost_bps_per_leg"] for t in trials] == [0.0, 10.0, 20.0]
    assert all(counts_for_deflation(t) for t in trials)
    sharpes = trial_sharpes(trials, "validation")
    assert len(sharpes) == 3 and sharpes[0] > sharpes[1] > sharpes[2]
    last = records[-1].manifest["deflated_sharpe"]["validation"]
    assert last["n_trials"] == 3 and last["n_defined"] == 3
    assert last["sharpe_variance"] == pytest.approx(float(np.var(sharpes, ddof=1)))
    assert 0.0 <= last["dsr"] <= 1.0
    # the second run was deflated with the two trials that existed then
    assert records[1].manifest["deflated_sharpe"]["validation"]["n_trials"] == 2
    gross = [r.manifest["metrics"]["full"]["gross_sharpe"] for r in records]
    assert gross[0] == pytest.approx(gross[1]) == pytest.approx(gross[2])


def test_basket_backtest(runner: Backtester) -> None:
    analysis = runner.analyser.analyse_basket()
    assert analysis.outcome == "ok" and analysis.tickers == ("KO", "PEP", "KDP")
    assert analysis.johansen.nobs == int((CALENDAR.tz_localize(None) < "2018-01-01").sum())
    assert analysis.screen_passed is (analysis.johansen.rank_trace >= 1)
    record = runner.backtest_basket()
    man = record.manifest
    assert record.outcome == "ok" and man["strategy"] == "basket"
    assert man["hedge"] == "johansen" and man["tickers"] == ["KO", "PEP", "KDP"]
    assert man["settings"]["neutrality"] == "eigenvector"
    assert man["screen"]["status"] == ("pass" if analysis.screen_passed else "fail")
    assert man["screen"]["trial_id"] == analysis.trial_id
    windows = read_table(runner.project.runs_dir, record.run_id, "windows")
    assert {"rank_trace", "weight_KO", "weight_PEP", "weight_KDP"} <= set(windows.columns)
    kinds = [t.kind for t in runner.log.read()]
    assert kinds == ["basket_analysis", "backtest"]
    assert runner.log.read()[0].results["screen"]["criteria"][0]["name"] == "johansen_rank"


def test_simulated_controls_and_batches_do_not_count_as_attempts(
    runner: Backtester,
) -> None:
    runner.analyse_simulated("cointegrated")
    runner.analyse_simulated("cointegrated")  # second call adds nothing
    assert runner.log.count(kind="pair_analysis") == 1
    single = runner.backtest_simulated("cointegrated")
    man = single.manifest
    assert man["tickers"] == ["SIM_A", "SIM_B"] and man["label"] == "synthetic"
    assert man["data_source"] == "synthetic" and man["survivorship_bias"] is False
    assert man["deflated_sharpe"] is None and man["provenance"]["snapshot_ids"] == {}
    assert man["settings"]["seed"] == 20261111 and man["settings"]["half_life"] == 10.0
    assert man["screen"]["status"] in ("pass", "fail")
    assert man["metrics"]["validation"] is None  # 800 simulated rows end in 2013
    assert man["metrics"]["full"]["beta_to_benchmark"] is None  # no benchmark
    batch = runner.control_batch("random_walk", hedge="rolling")
    assert batch.kind == "control_batch" and batch.manifest["control"] == "random_walk"
    assert batch.manifest["summary"]["n_seeds"] == 3
    seeds = read_table(runner.project.runs_dir, batch.run_id, "seeds")
    assert list(seeds["seed"]) == [30000, 30001, 30002]
    trials = runner.log.read()
    assert trials[-1].tickers == ("random_walk_batch",)
    assert trials[-1].parameters["batch"] == {
        "kind": "random_walk", "first_seed": 30000, "size": 3,
    }
    assert not any(counts_for_deflation(t) for t in trials)


def test_placebo_batch_ranks_the_real_run(runner: Backtester) -> None:
    real = runner.backtest_pair("AAA", "BBB")
    placebo = runner.placebo_batch("AAA", "BBB", real=real)
    man = placebo.manifest
    assert placebo.kind == "control_batch" and man["control"] == "placebo"
    assert man["label"] == "control" and man["real_run_id"] == real.run_id
    assert man["real_sharpe"] == real.manifest["metrics"]["full"]["sharpe"]
    seeds = read_table(runner.project.runs_dir, placebo.run_id, "seeds")
    assert list(seeds["seed"]) == [40000, 40001, 40002]
    at_least = int((seeds["sharpe"] >= man["real_sharpe"]).sum())
    assert set(man["rank"]) == {"full", "formation", "validation"}
    assert man["rank"]["full"]["real_sharpe"] == man["real_sharpe"]
    assert man["rank"]["full"]["share_at_least"] == pytest.approx((1 + at_least) / 4)
    real_validation = real.manifest["metrics"]["validation"]["sharpe"]
    assert man["rank"]["validation"]["real_sharpe"] == real_validation
    at_least = int((seeds["sharpe_validation"] >= real_validation).sum())
    assert man["rank"]["validation"]["share_at_least"] == pytest.approx((1 + at_least) / 4)
    trial = runner.log.read()[-1]
    assert trial.parameters["placebo"] == {
        "first_seed": 40000, "shuffles": 3, "legs": "both", "real_run_id": real.run_id,
    }
    assert not counts_for_deflation(trial) and counts_for_deflation(runner.log.read()[0])


def test_run_demo_runs_everything_once(runner: Backtester) -> None:
    assert not runner.demo_already_run()
    records = runner.run_demo()
    assert all(r.outcome == "ok" for r in records)
    backtests = [r for r in records if r.kind == "backtest"]
    batches = [r for r in records if r.kind == "control_batch"]
    # 6 pairs x 3 hedges x 3 costs, 3 basket costs, 2 simulated pairs x 3 x 3
    assert len(backtests) == 54 + 3 + 18
    # 2 kinds x 3 hedges of simulated batches, and one placebo batch per pair
    assert len(batches) == 6 + 6
    trials = runner.log.read()
    by_kind = pd.Series([t.kind for t in trials]).value_counts().to_dict()
    # the six real pairs and the two simulated ones are screened first, once each
    assert by_kind == {"backtest": 75 + 12, "pair_analysis": 8, "basket_analysis": 1}
    assert sum(counts_for_deflation(t) for t in trials) == 57
    assert runner.demo_already_run()
    labels = {tuple(r.manifest["tickers"]): r.manifest["label"] for r in backtests}
    assert labels[("V", "XOM")] == "control" and labels[("KO", "PEP")] == "case_study"
    assert labels[("SIM_A", "SIM_B")] == "synthetic"
    assert labels[("KO", "PEP", "KDP")] == "case_study"
    last_real = [r for r in backtests if r.manifest["data_source"] == "yfinance"][-1]
    assert last_real.manifest["deflated_sharpe"]["validation"]["n_trials"] == 57

    summary = runner.summarise()
    assert summary.kind == "summary" and runner.log.count() == len(trials)  # no trial
    man = summary.manifest
    assert len(man["rows"]) == 75 and man["n_trials_counted"] == 57
    real_rows = [r for r in man["rows"] if r["data_source"] == "yfinance"]
    assert all(r["deflated_sharpe"]["validation"]["n_trials"] == 57 for r in real_rows)
    assert all(r["deflated_sharpe"] is None for r in man["rows"] if r not in real_rows)
    # every real run carries a screen result: run_demo screens before it backtests
    statuses = {tuple(r["tickers"]): r["screen_status"] for r in real_rows}
    assert set(statuses.values()) <= {"pass", "fail"}
    assert all(r["screen_status"] == r["screen_status_at_run"] for r in real_rows)
    # candidates: the five case-study pairs and the basket, not the control pair
    head = man["headline"]
    assert head["n_candidates"] == 6 and head["complete"] is True
    assert [tuple(e["tickers"]) for e in head["candidates"]] == [
        ("V", "MA"), ("KO", "PEP"), ("XOM", "CVX"), ("HD", "LOW"), ("EWA", "EWC"),
        ("KO", "PEP", "KDP"),
    ]
    assert set(head["candidate_states"]) <= {"held", "failed"}
    assert sum(head["candidate_states"].values()) == 6
    passed = [t for t, st in statuses.items() if st == "pass" and t != ("V", "XOM")]
    assert head["n_runs"] == len(passed) and head["duplicate_run_ids_ignored"] == []
    if passed:
        assert head["metrics"]["validation"] is not None
    else:
        assert head["metrics"] is None
        assert head["statement"].startswith("All 6 pre-registered candidates were screened")
        assert "takes no positions" in head["statement"]
    # running the demo a second time does not screen anything again
    n_analyses = runner.log.count(kind="pair_analysis")
    runner.analyse_simulated("random_walk")
    assert runner.log.count(kind="pair_analysis") == n_analyses


def _analysis_trial(runner: Backtester, tickers: tuple[str, ...], passed: bool) -> None:
    """Write a formation-period analysis line with a chosen screen result."""
    runner.log.record(
        kind="pair_analysis", label="case_study", tickers=tickers,
        period={"name": "formation", "start": "2010-01-01", "asof": "2018-01-01"},
        data_source="yfinance", survivorship_bias=True, snapshot_ids={},
        config_hashes={}, code_commit="c", code_dirty=False,
        test_period_touched=False, unlock=None, outcome="ok",
        results={"screen": {"passed": passed, "criteria": []}},
    )


def test_headline_is_the_screened_candidates_once_each(runner: Backtester) -> None:
    """The headline holds pre-registered runs that passed the screen, at the
    default hedge and cost, one per pair, and reports what is out of sample."""
    _analysis_trial(runner, ("KO", "PEP"), True)
    _analysis_trial(runner, ("HD", "LOW"), False)
    chosen = runner.backtest_pair("KO", "PEP")
    runner.backtest_pair("KO", "PEP", cost_bps=20.0)  # not the default cost
    runner.backtest_pair("KO", "PEP", hedge="kalman")  # not the default hedge
    runner.backtest_pair("HD", "LOW")  # failed the screen
    alone = runner.summarise().manifest["headline"]
    assert alone["run_ids"] == [chosen.run_id] and alone["n_candidates"] == 6
    assert alone["candidate_states"] == {"held": 1, "failed": 1, "no_stored_run": 4}
    assert alone["out_of_sample_span"] == "validation"
    assert alone["spans_in_sample_for_screen"] == ["full", "formation"]
    for span in ("full", "formation", "validation"):
        mine, theirs = alone["metrics"][span], chosen.manifest["metrics"][span]
        assert mine["sharpe"] == pytest.approx(theirs["sharpe"])
        assert mine["total_return"] == pytest.approx(theirs["total_return"])
        assert mine["n_trades"] == theirs["n_trades"]
        # the headline has a beta to SPY and a Deflated Sharpe ratio of its own
        assert mine["beta_to_benchmark"] == pytest.approx(theirs["beta_to_benchmark"])
        assert alone["deflated_sharpe"][span]["n_trials"] == 4

    # the same pair again, and with its legs swapped: still held once
    again = runner.backtest_pair("KO", "PEP")
    swapped = runner.backtest_pair("PEP", "KO")
    _analysis_trial(runner, ("V", "MA"), True)
    second = runner.backtest_pair("V", "MA")
    # a pair the user chose that passed the screen is listed but never held
    _analysis_trial(runner, ("AAA", "BBB"), True)
    exploratory = runner.backtest_pair("AAA", "BBB")
    # a case_study label given by hand to a pair that is not in pairs.yaml
    _analysis_trial(runner, ("BIGDIV", "BBB"), True)
    unlisted = runner.backtest_pair("BIGDIV", "BBB", label="case_study")
    man = runner.summarise().manifest
    head = man["headline"]
    assert head["run_ids"] == [second.run_id, chosen.run_id] and head["n_runs"] == 2
    assert head["duplicate_run_ids_ignored"] == [again.run_id, swapped.run_id]
    assert man["exploratory_screened_run_ids"] == [exploratory.run_id]
    assert man["unlisted_case_study_run_ids"] == [unlisted.run_id]
    both = [chosen.manifest["metrics"]["validation"], second.manifest["metrics"]["validation"]]
    assert head["metrics"]["validation"]["total_return"] == pytest.approx(
        (both[0]["total_return"] + both[1]["total_return"]) / 2
    )
    assert head["metrics"]["validation"]["n_trades"] == both[0]["n_trades"] + both[1]["n_trades"]


def test_headline_names_every_candidate_that_is_missing(
    runner: Backtester, downloader: FakeDownloader
) -> None:
    """The headline is stated against the list in configs/pairs.yaml: a candidate
    with no stored run, a refused run or no screen result is named, also when
    another candidate is held."""
    empty = runner.summarise().manifest["headline"]
    assert empty["candidate_states"] == {"no_stored_run": 6} and not empty["complete"]
    assert "cannot be stated yet" in empty["statement"]
    assert "6 of the 6 have no stored backtest" in empty["statement"]
    assert "KO/PEP/KDP" in empty["statement"]

    runner.backtest_pair("KO", "PEP")  # backtested but never screened
    frame = downloader.frames["HD"]
    downloader.frames["HD"] = frame.drop(frame.index[[400, 401]])
    refused = runner.backtest_pair("HD", "LOW")  # stopped by a data check
    assert refused.outcome == "refused"
    head = runner.summarise().manifest["headline"]
    assert head["candidate_states"] == {"no_screen_result": 1, "no_stored_run": 5}
    assert "1 of the 6 have no usable formation-period screen result: KO/PEP." in (
        head["statement"]
    )
    assert "HD/LOW (refused: Data checks failed: HD is missing 2 trading days" in (
        head["statement"]
    )
    assert "none passed" not in head["statement"] and head["metrics"] is None

    # one candidate passes and is held: the others are still named
    _analysis_trial(runner, ("V", "MA"), True)
    held = runner.backtest_pair("V", "MA")
    head = runner.summarise().manifest["headline"]
    assert head["run_ids"] == [held.run_id] and not head["complete"]
    assert head["statement"].startswith("Equal-weight portfolio of the 1 pre-registered")
    assert "of 6 named in configs/pairs.yaml" in head["statement"]
    assert "no usable formation-period screen result: KO/PEP." in head["statement"]
    assert "4 of the 6 have no stored backtest" in head["statement"]


def test_headline_when_every_candidate_was_screened_and_failed(runner: Backtester) -> None:
    for tickers in runner.preregistered_candidates():
        _analysis_trial(runner, tickers, False)
        if len(tickers) == 2:
            runner.backtest_pair(*tickers)
        else:
            runner.backtest_basket(list(tickers))
    head = runner.summarise().manifest["headline"]
    assert head["candidate_states"] == {"failed": 6} and head["complete"] is True
    assert head["statement"] == (
        "All 6 pre-registered candidates were screened on the formation period and "
        "none passed, so the strategy as stated in advance takes no positions. There "
        "is no headline return to report."
    )
    assert head["metrics"] is None and head["n_runs"] == 0


@pytest.mark.parametrize(("at_run", "later"), [(False, True), (True, False)])
def test_a_screen_result_that_changed_after_the_backtest_is_not_held(
    runner: Backtester, at_run: bool, later: bool
) -> None:
    """Screening a pair again after seeing its backtest must not change who is
    in the headline: the run is left out either way and the statement says so."""
    _analysis_trial(runner, ("KO", "PEP"), at_run)
    record = runner.backtest_pair("KO", "PEP")
    assert record.manifest["screen"]["status"] == ("pass" if at_run else "fail")
    _analysis_trial(runner, ("KO", "PEP"), later)
    head = runner.summarise().manifest["headline"]
    entry = next(e for e in head["candidates"] if e["tickers"] == ["KO", "PEP"])
    assert entry["state"] == "screen_changed" and entry["run_id"] == record.run_id
    assert entry["screen_status"] != entry["screen_status_at_run"]
    assert head["n_runs"] == 0 and head["metrics"] is None
    assert "screen result changed after they were backtested: KO/PEP." in head["statement"]


def test_screened_candidates_that_were_dropped_count_as_trials(runner: Backtester) -> None:
    """Analysing a real pair and not backtesting it is still an attempt."""
    runner.backtest_pair("AAA", "BBB", cost_bps=0.0)
    runner.backtest_pair("AAA", "BBB")
    assert len(trial_sharpes(runner.log.read(), "validation")) == 2
    runner.analyser.analyse_pair("KO", "PEP")
    runner.analyser.analyse_pair("PEP", "KO")  # the same candidate again
    runner.analyser.analyse_pair("BBB", "AAA")  # already backtested
    runner.analyser.analyse_synthetic()  # simulated: not a real candidate
    trials = runner.log.read()
    assert screened_not_backtested(trials) == [("KO", "PEP")]
    sharpes = trial_sharpes(trials, "validation")
    assert len(sharpes) == 3 and int(np.isnan(sharpes).sum()) == 1
    record = runner.backtest_pair("AAA", "BBB", cost_bps=20.0)
    deflated = record.manifest["deflated_sharpe"]["validation"]
    assert deflated["n_trials"] == 4 and deflated["n_defined"] == 3
    man = runner.summarise().manifest
    assert man["n_backtests_counted"] == 3 and man["n_trials_counted"] == 4
    assert man["screened_not_backtested"] == [["KO", "PEP"]]


def test_as_of_in_the_locked_test_period_is_refused(runner: Backtester) -> None:
    """The runner cannot be pointed past the lock: the price source refuses the
    as-of date before any row is read, and nothing is logged or stored."""
    runner.analyser.ensure_cached(["AAA", "BBB", "SPY"], offline=False)
    runner.asof = pd.Timestamp("2023-01-01")
    with pytest.raises(LockedPeriodError):
        runner.backtest_pair("AAA", "BBB")
    with pytest.raises(LockedPeriodError):
        runner.backtest_basket(["AAA", "BBB", "SPY"])
    assert runner.log.count() == 0 and list_runs(runner.project.runs_dir) == []


def test_an_engine_failure_is_logged_as_an_error(
    runner: Backtester, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*args: object, **kwargs: object) -> None:
        raise ValueError("boom")

    monkeypatch.setattr("statarb_agent.backtest.runner.run_pair_backtest", broken)
    record = runner.backtest_pair("AAA", "BBB")
    assert record.outcome == "error" and record.reason == "backtest failed: boom"
    assert record.path is None and list_runs(runner.project.runs_dir) == []
    (trial,) = runner.log.read()
    assert trial.outcome == "error" and not counts_for_deflation(trial)


def test_equal_weight_portfolio_by_hand() -> None:
    idx = pd.bdate_range("2020-01-01", periods=3, name="date")

    def daily(pnl: list[float], position: list[int]) -> pd.DataFrame:
        frame = pd.DataFrame({"pnl": pnl, "position": position}, index=idx)
        for column in ("price_pnl", "gross_pnl"):
            frame[column] = frame["pnl"] + 1.0
        for column in ("dist_pnl", "borrow_cost", "trade_cost", "traded_notional",
                       "gross_exposure", "net_exposure"):
            frame[column] = 0.5
        return frame

    def trades(net: float) -> pd.DataFrame:
        return pd.DataFrame({"price_pnl": [net], "dist_pnl": [0.0], "borrow_cost": [0.0],
                             "trade_cost": [0.0], "net_pnl": [net]})

    out, pooled = equal_weight_portfolio(
        [daily([10.0, 0.0, -4.0], [1, 0, 0]), daily([2.0, 6.0, 0.0], [0, 0, 0])],
        [trades(6.0), trades(8.0)], capital=100.0,
    )
    np.testing.assert_allclose(out["pnl"], [6.0, 3.0, -2.0])
    np.testing.assert_allclose(out["ret"], [0.06, 0.03, -0.02])
    np.testing.assert_allclose(out["gross_ret"], [0.07, 0.04, -0.01])
    assert list(out["position"]) == [1, 0, 0]
    assert list(pooled["net_pnl"]) == [3.0, 4.0]
    with pytest.raises(ValueError):
        equal_weight_portfolio([], [], capital=100.0)
    shifted = daily([1.0, 1.0, 1.0], [0, 0, 0])
    shifted.index = shifted.index + pd.Timedelta(days=7)
    with pytest.raises(ValueError, match="different dates"):
        equal_weight_portfolio([daily([1.0] * 3, [0] * 3), shifted], [], capital=100.0)


# CLI -----------------------------------------------------------------------

cli_runner = CliRunner()


@pytest.fixture
def cli_env(
    project: Project, downloader: FakeDownloader, monkeypatch: pytest.MonkeyPatch
) -> Project:
    monkeypatch.setattr(
        "statarb_agent.sources.prices.make_yfinance_downloader",
        lambda cache_dir, **kwargs: downloader,
    )
    return project


def invoke(project: Project, *args: str):
    return cli_runner.invoke(cli.app, ["--root", str(project.root), *args])


def test_cli_backtest_and_runs(cli_env: Project) -> None:
    result = invoke(cli_env, "backtest", "aaa", "bbb")
    assert result.exit_code == 0, result.output
    out = result.output
    assert "AAA / BBB   backtest, hedge static, 10 bps per leg" in out
    assert "EXPLORATORY" in out and "survivorship bias" in out
    assert "downloaded AAA just now" in out
    assert "Formation-period screen: not_analysed" in out
    assert "formation (" in out and "validation (2018-01-01 to 2021-12-31)" in out
    assert "Deflated Sharpe n/a (1 trials so far)" in out and "Costs are included" in out
    assert "only the validation span is out of sample" in out
    trial = TrialLog(cli_env.trials_path).read()[0]
    assert trial.trial_id in out and trial.kind == "backtest"

    as_json = invoke(cli_env, "backtest", "AAA", "BBB", "--hedge", "kalman",
                     "--cost-bps", "0", "--offline", "--json")
    assert as_json.exit_code == 0, as_json.output
    payload = json.loads(as_json.output)
    assert payload["manifest"]["hedge"] == "kalman" and payload["manifest"]["cost_bps"] == 0

    listing = invoke(cli_env, "runs")
    assert listing.exit_code == 0 and listing.output.count("AAA/BBB [exploratory]") == 2
    assert TrialLog(cli_env.trials_path).count() == 2  # listing adds no trial

    assert invoke(cli_env, "backtest", "AAA", "BBB", "--hedge", "magic").exit_code == 1
    assert invoke(cli_env, "backtest", "AAA", "BBB", "--cost-bps", "-1").exit_code == 1
    assert invoke(cli_env, "backtest", "AAA", "AAA").exit_code == 1
    refused = invoke(cli_env, "backtest", "AAA", "GAP")
    assert refused.exit_code == 2 and "REFUSED" in refused.output
    assert TrialLog(cli_env.trials_path).count() == 3


def test_cli_runs_with_nothing_stored(cli_env: Project) -> None:
    result = invoke(cli_env, "runs")
    assert result.exit_code == 0 and "No stored runs" in result.output


def test_cli_validation_period_is_open_and_test_is_not(cli_env: Project) -> None:
    result = invoke(cli_env, "analyse", "AAA", "BBB", "--period", "validation")
    assert result.exit_code == 0, result.output
    assert "period validation: 2018-01-01 up to (not including) 2022-01-01" in result.output
    refused = invoke(cli_env, "analyse", "AAA", "BBB", "--period", "test")
    assert refused.exit_code == 1 and "locked" in refused.output


def test_cli_backtest_demo_refuses_a_second_run(cli_env: Project) -> None:
    first = invoke(cli_env, "backtest-demo")
    assert first.exit_code == 0, first.output
    assert "KO/PEP [case_study] static 10bps" in first.output
    assert "[placebo batch]" in first.output and "[random_walk batch]" in first.output
    summaries = [m for m in list_runs(cli_env.runs_dir) if m["kind"] == "summary"]
    assert summaries[-1]["headline"]["statement"] in first.output
    assert "Summary: " in first.output
    n_trials = TrialLog(cli_env.trials_path).count()
    second = invoke(cli_env, "backtest-demo")
    assert second.exit_code == 1 and "already holds the demo backtests" in second.output
    assert TrialLog(cli_env.trials_path).count() == n_trials
    summary = invoke(cli_env, "summarise")
    assert summary.exit_code == 0 and "57 real-data backtest trials" in summary.output
    assert TrialLog(cli_env.trials_path).count() == n_trials
    kinds = [m["kind"] for m in list_runs(cli_env.runs_dir)]
    assert kinds.count("summary") == 2 and kinds.count("backtest") == 75

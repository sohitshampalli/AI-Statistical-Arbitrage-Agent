"""Tests for the dashboard's read-only result store, on a fake project."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fake_results import make_results, make_runner

from statarb_agent.api.store import ResultStore, downloaded_before_terms_check
from statarb_agent.backtest.runner import screen_status, trial_sharpes
from statarb_agent.backtest.runs import RunError
from statarb_agent.sources.base import Manifest


@pytest.fixture
def results(tmp_path: Path):
    return make_results(tmp_path)


def test_runs_lists_every_stored_run_with_its_provenance(results) -> None:
    store = ResultStore(results.project.root)
    runs = store.runs()
    ids = [r["run_id"] for r in runs]
    assert ids == sorted(ids)
    assert results.pair_run.run_id in ids and results.summary.run_id in ids
    pair = next(r for r in runs if r["run_id"] == results.pair_run.run_id)
    assert pair["kind"] == "backtest" and pair["tickers"] == ["AAA", "BBB"]
    assert pair["label"] == "exploratory" and pair["hedge"] == "static"
    assert pair["cost_bps"] == 10.0 and pair["data_source"] == "yfinance"
    assert pair["code_commit"] == results.pair_run.manifest["provenance"]["code_commit"]
    summary = next(r for r in runs if r["run_id"] == results.summary.run_id)
    assert summary["kind"] == "summary" and summary["tickers"] is None


def test_run_and_table_read_through_the_hash_check(results) -> None:
    store = ResultStore(results.project.root)
    run_id = results.pair_run.run_id
    assert store.run(run_id) == results.pair_run.manifest
    daily = store.table(run_id, "daily")
    assert len(daily) == store.run(run_id)["files"]["daily"]["rows"]
    with pytest.raises(RunError, match="no table"):
        store.table(run_id, "secrets")
    with pytest.raises(ValueError, match="invalid run id"):
        store.run("../../etc")
    path = results.project.runs_dir / run_id / "trades.parquet"
    path.write_bytes(path.read_bytes() + b"x")
    with pytest.raises(RunError, match="does not match"):
        store.table(run_id, "trades")


def test_latest_summary_is_the_newest(results) -> None:
    store = ResultStore(results.project.root)
    assert store.latest_summary()["run_id"] == results.summary.run_id
    newer = results.runner.summarise()
    assert store.latest_summary()["run_id"] == newer.run_id
    assert [s["run_id"] for s in store.summaries()] == [
        results.summary.run_id, newer.run_id,
    ]


def test_no_summary_is_none(tmp_path: Path) -> None:
    runner = make_runner(tmp_path)
    assert ResultStore(runner.project.root).latest_summary() is None
    assert ResultStore(runner.project.root).runs() == []


def test_trial_stats_use_the_runner_counting_rules(results) -> None:
    store = ResultStore(results.project.root)
    trials = store.trials()
    stats = store.trial_stats()
    assert stats["n_lines"] == len(trials)
    assert sum(stats["by_kind"].values()) == len(trials)
    assert sum(stats["by_label"].values()) == len(trials)
    assert stats["by_kind"]["pair_analysis"] == 1  # V/MA
    # the same N the runner deflates with: one entry per counted attempt
    assert stats["n_counted"] == len(trial_sharpes(trials, "validation"))
    # V/MA was analysed and never backtested: one attempt with unknown Sharpe
    assert stats["n_screened_not_backtested"] == 1
    assert stats["n_backtests_counted"] == 1  # AAA/BBB
    # a fake project is not a git repository, so the code state is unknown: dirty
    assert stats["dirty_lines"] == list(range(1, len(trials) + 1))


def test_configs_report_text_and_hash(results) -> None:
    store = ResultStore(results.project.root)
    configs = {c["name"]: c for c in store.configs()}
    assert set(configs) == {"study", "screen", "data", "pairs", "backtest"}
    assert {n: c["sha256"] for n, c in configs.items()} == results.project.config_hashes()
    assert configs["backtest"]["path"] == "configs/backtest.yaml"
    assert configs["backtest"]["text"] == results.project.backtest_path.read_text()


def test_pairs_carry_the_screen_status_from_the_trial_log(results) -> None:
    store = ResultStore(results.project.root)
    pairs = store.pairs()
    trials = store.trials()
    by_name = {(p["a"], p["b"]): p for p in pairs["pairs"]}
    assert by_name[("V", "MA")]["screen"] == screen_status(trials, ("V", "MA"))
    assert by_name[("V", "MA")]["screen"]["status"] in ("pass", "fail")
    assert by_name[("KO", "PEP")]["screen"]["status"] == "not_analysed"
    assert by_name[("V", "XOM")]["label"] == "control"
    assert pairs["basket"]["tickers"] == ["KO", "PEP", "KDP"]
    assert pairs["synthetic"]["label"] == "synthetic"


def test_snapshots_report_provenance_and_presence(results) -> None:
    store = ResultStore(results.project.root)
    snaps = store.snapshots()
    keys = {s["key"] for s in snaps}
    assert {"V", "MA", "AAA", "BBB", "SPY"} <= keys
    assert all(s["source"] == "yfinance" and s["file_present"] for s in snaps)
    # the fake clock is 2026-11-10, before the terms check of 2026-11-23
    assert all(s["downloaded_before_terms_check"] is True for s in snaps)
    assert store.cached_tickers() == sorted(keys)

    # a fresh clone has the manifest but no files: not offered as cached
    entry = Manifest(results.project.data_dir / "manifest.json").latest("yfinance", "MA")
    (results.project.data_dir / entry.path).unlink()
    assert "MA" not in store.cached_tickers()
    assert next(s for s in store.snapshots() if s["key"] == "MA")["file_present"] is False


def test_terms_check_flag_follows_the_retrieval_time(tmp_path: Path) -> None:
    after = pd.Timestamp("2026-11-24T00:00:00", tz="UTC")
    runner = make_runner(tmp_path, clock=lambda: after)
    runner.analyser.ensure_cached(["SPY"], offline=False)
    (entry,) = Manifest(runner.project.data_dir / "manifest.json").entries()
    assert downloaded_before_terms_check(entry) is False
    unknown = entry.__class__(**{**entry.__dict__, "source": "other"})
    assert downloaded_before_terms_check(unknown) is None


def test_sources_report_the_download_switch() -> None:
    (yahoo,) = ResultStore(Path(".")).sources()
    assert yahoo.name == "yfinance" and yahoo.downloads_enabled is False
    assert yahoo.terms_checked_on == "2026-11-23"
    assert "before the terms check" in yahoo.terms_note

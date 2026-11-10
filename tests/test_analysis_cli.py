"""End-to-end tests of the analysis path and the CLI, on synthetic snapshots.

Each test builds a throwaway project folder (configs copied from the repo, an
empty data folder and trial log) and a fake downloader that returns frames
shaped like yfinance output. Nothing touches the network or the real data
folder or the real trial log.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from statarb_agent import cli
from statarb_agent.analysis import Analyser, OfflineError
from statarb_agent.data.synthetic import simulate_cointegrated_pair
from statarb_agent.project import Project, load_data_config, load_pairs
from statarb_agent.sources.base import SnapshotStore
from statarb_agent.sources.prices import YFinancePrices
from statarb_agent.study import LockedPeriodError, load_study
from statarb_agent.trials import TrialLog

REPO_ROOT = Path(__file__).resolve().parents[1]
CALENDAR = pd.bdate_range("2010-01-04", "2021-12-31", tz="America/New_York", name="Date")
ASOF = pd.Timestamp("2018-01-01")  # formation as-of; a Monday, so a row has this date
N_FORMATION = int((CALENDAR.tz_localize(None) < ASOF).sum())
DEMO_TICKERS = ("V", "MA", "KO", "PEP", "XOM", "CVX", "HD", "LOW", "EWA", "EWC")


def frame_from_close(close: np.ndarray, dividends: np.ndarray | None = None) -> pd.DataFrame:
    """A frame shaped like Ticker.history(auto_adjust=False, actions=True)."""
    n = len(close)
    div = np.zeros(n) if dividends is None else dividends
    return pd.DataFrame(
        {
            "Open": close, "High": close * 1.01, "Low": close * 0.99, "Close": close,
            "Adj Close": close, "Volume": np.full(n, 1000, dtype="int64"),
            "Dividends": div, "Stock Splits": np.zeros(n),
        },
        index=CALENDAR[:n] if n <= len(CALENDAR) else None,
    )


def walk(seed: int, start: float = 80.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return start * np.exp(np.cumsum(0.01 * rng.standard_normal(len(CALENDAR))))


def base_frames() -> dict[str, pd.DataFrame]:
    """AAA and BBB are cointegrated (beta 1.5, half-life 10); the rest are walks."""
    pair = simulate_cointegrated_pair(seed=11, n_obs=len(CALENDAR))
    dividends = np.zeros(len(CALENDAR))
    dividends[40::63] = 0.25
    frames = {
        "AAA": frame_from_close(np.exp(pair["log_a"].to_numpy()), dividends),
        "BBB": frame_from_close(np.exp(pair["log_b"].to_numpy())),
        "SPY": frame_from_close(walk(1, 200.0)),
    }
    for i, ticker in enumerate(DEMO_TICKERS):
        frames[ticker] = frame_from_close(walk(100 + i))
    gap = frame_from_close(walk(3))
    frames["GAP"] = gap.drop(gap.index[[300, 301, 950]])
    late = frame_from_close(walk(4))
    frames["LATE"] = late.loc[late.index >= "2012-06-01"]
    big = np.zeros(len(CALENDAR))
    big[500] = 0.3 * walk(5)[499]
    frames["BIGDIV"] = frame_from_close(walk(5), big)
    frames["NODATA"] = frame_from_close(walk(6)).iloc[:0]
    return frames


class FakeDownloader:
    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self.frames = frames
        self.calls: list[tuple[str, str, str]] = []

    def __call__(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        self.calls.append((ticker, start, end))
        return self.frames[ticker].copy()


@pytest.fixture
def project(tmp_path: Path) -> Project:
    root = tmp_path / "project"
    shutil.copytree(REPO_ROOT / "configs", root / "configs")
    path = root / "configs" / "data.yaml"
    path.write_text(path.read_text().replace("pause_seconds: 2.0", "pause_seconds: 0.0"))
    return Project(root)


@pytest.fixture
def downloader() -> FakeDownloader:
    return FakeDownloader(base_frames())


@pytest.fixture
def analyser(project: Project, downloader: FakeDownloader) -> Analyser:
    study = load_study(project.study_path)
    source = YFinancePrices(
        SnapshotStore(project.data_dir, repo_root=project.root), study=study,
        downloader=downloader, pause_s=0.0,
    )
    return Analyser(project, source=source, log=TrialLog(project.trials_path))


# Configs -------------------------------------------------------------------


def test_project_configs_load() -> None:
    project = Project(REPO_ROOT)
    data = load_data_config(project.data_config_path)
    assert data.reference_calendar == "SPY" and data.download_start == "2010-01-01"
    assert (data.min_obs, data.max_unmatched_days, data.stale_run) == (252, 0, 5)
    assert (data.max_abs_log_return, data.max_distribution_fraction) == (0.4, 0.10)
    pairs = load_pairs(project.pairs_path)
    assert [(p.a, p.b, p.label) for p in pairs.pairs] == [
        ("V", "MA", "case_study"), ("KO", "PEP", "case_study"),
        ("XOM", "CVX", "case_study"), ("HD", "LOW", "case_study"),
        ("EWA", "EWC", "case_study"), ("V", "XOM", "control"),
    ]
    assert pairs.basket == ("KO", "PEP", "KDP")
    assert pairs.synthetic.seed == 20261110 and pairs.synthetic.n_obs == 2013
    assert pairs.label_for("PEP", "KO") == "case_study"
    assert pairs.label_for("XOM", "V") == "control"
    assert pairs.label_for("KO", "XOM") == "exploratory"
    assert pairs.tickers() == (*DEMO_TICKERS, "KDP")
    assert sorted(project.config_hashes()) == ["data", "pairs", "screen", "study"]


@pytest.mark.parametrize(
    ("name", "old", "new"),
    [
        ("data", "min_obs: 252", "min_obs: 2.5"),
        ("data", "min_obs: 252", "min_obs: 5"),
        ("data", "stale_run: 5", "stale_run: true"),
        ("data", "reference_calendar: SPY", "reference_calendar: ../x"),
        ("data", "pause_seconds: 2.0", "pause_seconds: -1"),
        ("data", "pause_seconds: 2.0", "pause_seconds: 2.0\nextra: 1"),
        ("pairs", "{a: V, b: MA, label: case_study}", "{a: V, b: V, label: case_study}"),
        ("pairs", "{a: EWA, b: EWC, label: case_study}",
         "{a: MA, b: V, label: case_study}"),
        ("pairs", "label: control", "label: exploratory"),
        ("pairs", "seed: 20261110", "seed: -1"),
        ("pairs", "basket: [KO, PEP, KDP]", "basket: [KO, PEP]"),
        ("pairs", "basket: [KO, PEP, KDP]", "basket: [KO, PEP, KO]"),
    ],
)
def test_bad_configs_raise(tmp_path: Path, name: str, old: str, new: str) -> None:
    text = (REPO_ROOT / "configs" / f"{name}.yaml").read_text()
    assert old in text
    path = tmp_path / f"{name}.yaml"
    path.write_text(text.replace(old, new))
    loader = load_data_config if name == "data" else load_pairs
    with pytest.raises((ValueError, TypeError)):
        loader(path)


# Analyser ------------------------------------------------------------------


def test_exploratory_pair_is_analysed_and_logged(
    analyser: Analyser, downloader: FakeDownloader
) -> None:
    result = analyser.analyse_pair("aaa", "bbb")
    assert result.outcome == "ok" and result.label == "exploratory"
    assert (result.ticker_a, result.ticker_b) == ("AAA", "BBB")
    assert result.downloaded == ("AAA", "BBB", "SPY")
    assert [c[0] for c in downloader.calls] == ["AAA", "BBB", "SPY"]
    assert all(c[1:] == ("2010-01-01", "2022-01-01") for c in downloader.calls)
    assert set(result.snapshot_ids) == {"AAA", "BBB", "SPY"}
    stats = result.stats
    assert stats is not None and stats.nobs == N_FORMATION
    assert stats.last_obs == "2017-12-29" and stats.asof == "2018-01-01"
    # AAA pays dividends, so its total-return price drifts above its price and
    # the hedge ratio is not exactly the simulated 1.5; the screen still applies.
    assert result.screen is not None and len(result.screen.criteria) == 3
    assert result.alignment is not None and result.alignment.n_common == N_FORMATION

    (trial,) = analyser.log.read()
    assert trial.trial_id == result.trial_id
    assert trial.kind == "pair_analysis" and trial.label == "exploratory"
    assert trial.tickers == ("AAA", "BBB") and trial.outcome == "ok"
    assert trial.survivorship_bias and trial.data_source == "yfinance"
    assert trial.snapshot_ids == result.snapshot_ids
    assert trial.period == {"name": "formation", "start": "2010-01-01",
                            "asof": "2018-01-01"}
    assert trial.config_hashes == analyser.project.config_hashes()
    assert not trial.test_period_touched and trial.unlock is None
    assert trial.results["stats"]["hedge"]["beta"] == stats.hedge.beta
    assert trial.results["screen"]["passed"] is result.screen.passed

    again = analyser.analyse_pair("AAA", "BBB")
    assert again.downloaded == () and len(downloader.calls) == 3
    assert again.result_dict() == result.result_dict()
    assert again.trial_id != result.trial_id and analyser.log.count() == 2


def test_demo_pair_gets_its_label_in_either_order(analyser: Analyser) -> None:
    assert analyser.analyse_pair("PEP", "KO").label == "case_study"
    assert analyser.analyse_pair("XOM", "V").label == "control"


def test_missing_days_refuse_and_are_logged(analyser: Analyser) -> None:
    result = analyser.analyse_pair("AAA", "GAP")
    assert result.outcome == "refused" and result.stats is None
    assert "GAP is missing 3 trading days" in result.reason
    (trial,) = analyser.log.read()
    assert trial.outcome == "refused" and trial.reason == result.reason
    assert trial.results["stats"] is None


def test_late_listing_refuses(analyser: Analyser) -> None:
    result = analyser.analyse_pair("LATE", "BBB")
    assert result.outcome == "refused"
    assert "LATE starts on 2012-06-01" in result.reason


def test_no_data_refuses_and_is_logged(analyser: Analyser) -> None:
    result = analyser.analyse_pair("AAA", "NODATA")
    assert result.outcome == "refused" and "No price data for NODATA" in result.reason
    assert analyser.log.count(outcome="refused") == 1


def test_anomaly_is_flagged_not_fatal(analyser: Analyser) -> None:
    result = analyser.analyse_pair("BIGDIV", "BBB")
    assert result.outcome == "ok" and result.stats is not None
    (flag,) = result.flags()
    assert flag.name == "large_distribution" and "BIGDIV" in flag.detail
    (trial,) = analyser.log.read()
    assert [f["name"] for f in trial.results["flags"]] == ["large_distribution"]


def test_offline_never_downloads(analyser: Analyser, downloader: FakeDownloader) -> None:
    with pytest.raises(OfflineError, match="statarb fetch AAA BBB SPY"):
        analyser.analyse_pair("AAA", "BBB", offline=True)
    assert downloader.calls == [] and analyser.log.count() == 0
    analyser.ensure_cached(["AAA", "BBB", "SPY"], offline=False)
    assert analyser.analyse_pair("AAA", "BBB", offline=True).outcome == "ok"


def test_missing_snapshot_file_is_fetched_again(
    analyser: Analyser, downloader: FakeDownloader
) -> None:
    """A fresh clone: the manifest lists a snapshot whose file is not there."""
    first = analyser.analyse_pair("AAA", "BBB")
    entry = analyser.source.entry_for("AAA")
    (analyser.source.store.root / entry.path).unlink()
    assert not analyser.is_cached("AAA")
    with pytest.raises(OfflineError, match="statarb fetch AAA"):
        analyser.analyse_pair("AAA", "BBB", offline=True)
    second = analyser.analyse_pair("AAA", "BBB")
    assert second.downloaded == ("AAA",)
    assert second.snapshot_ids["AAA"] != first.snapshot_ids["AAA"]
    assert second.result_dict() == first.result_dict()


def test_invalid_input_raises_and_logs_nothing(analyser: Analyser) -> None:
    with pytest.raises(ValueError, match="two different tickers"):
        analyser.analyse_pair("AAA", "aaa")
    with pytest.raises(ValueError):
        analyser.analyse_pair("../etc", "BBB")
    with pytest.raises(ValueError, match="unknown period"):
        analyser.analyse_pair("AAA", "BBB", period_name="test")
    assert analyser.log.count() == 0


def test_validation_period_is_available_in_the_library(analyser: Analyser) -> None:
    """The CLI blocks it for now; the library lock covers the test period only."""
    result = analyser.analyse_pair("AAA", "BBB", period_name="validation")
    assert result.outcome == "ok" and result.stats.first_obs == "2018-01-01"
    assert result.stats.last_obs == "2021-12-31"


def test_test_period_asof_is_refused_by_the_lock(analyser: Analyser) -> None:
    analyser.ensure_cached(["AAA"], offline=False)
    with pytest.raises(LockedPeriodError):
        analyser.source.load("AAA", asof="2023-01-01")


def test_synthetic_pair_is_analysed_without_data(analyser: Analyser) -> None:
    result = analyser.analyse_synthetic()
    assert result.label == "synthetic" and result.data_source == "synthetic"
    assert result.snapshot_ids == {} and result.checks == {}
    assert result.stats.nobs == 2013 and result.stats.last_obs < "2018-01-01"
    assert abs(result.stats.hedge.beta - 1.5) < 0.05  # Phase 1 bound for beta
    (trial,) = analyser.log.read()
    assert not trial.survivorship_bias and trial.parameters["seed"] == 20261110
    assert not result.to_dict()["record"]["survivorship_bias"]


# CLI -----------------------------------------------------------------------

runner = CliRunner()


@pytest.fixture
def cli_env(
    project: Project, downloader: FakeDownloader, monkeypatch: pytest.MonkeyPatch
) -> Project:
    """Point the CLI's default downloader at the fake one."""
    monkeypatch.setattr(
        "statarb_agent.sources.prices.make_yfinance_downloader",
        lambda cache_dir, **kwargs: downloader,
    )
    return project


def run(project: Project, *args: str) -> object:
    return runner.invoke(cli.app, ["--root", str(project.root), *args])


def test_cli_analyse_text_output(cli_env: Project) -> None:
    result = run(cli_env, "analyse", "aaa", "bbb")
    assert result.exit_code == 0, result.output
    out = result.output
    assert "AAA / BBB" in out and "EXPLORATORY" in out and "not pre-registered" in out
    assert "survivorship bias" in out
    assert "downloaded AAA just now" in out and "AAA: snapshot yfinance/AAA/" in out
    assert "Engle-Granger p-value, AAA on BBB" in out and "BBB on AAA" in out
    assert "Screen: " in out and "Trial log: " in out
    assert "formation window only" in out
    trial = TrialLog(cli_env.trials_path).read()[0]
    assert trial.trial_id in out
    second = run(cli_env, "analyse", "AAA", "BBB", "--offline")
    assert second.exit_code == 0 and "downloaded" not in second.output


def test_cli_refusals(cli_env: Project) -> None:
    result = run(cli_env, "analyse", "AAA", "BBB", "--period", "validation")
    assert result.exit_code == 1 and "not open" in result.output
    result = run(cli_env, "analyse", "AAA", "BBB", "--period", "test")
    assert result.exit_code == 1
    result = run(cli_env, "analyse", "AAA", "AAA")
    assert result.exit_code == 1 and "two different tickers" in result.output
    result = run(cli_env, "analyse", "AAA", "BBB", "--offline")
    assert result.exit_code == 1 and "statarb fetch" in result.output
    assert not cli_env.trials_path.exists()
    result = run(cli_env, "analyse", "AAA", "GAP")
    assert result.exit_code == 2 and "REFUSED" in result.output
    assert TrialLog(cli_env.trials_path).count(outcome="refused") == 1


def test_cli_fetch(cli_env: Project, downloader: FakeDownloader) -> None:
    result = run(cli_env, "fetch", "aaa", "BBB", "AAA")
    assert result.exit_code == 0, result.output
    assert [c[0] for c in downloader.calls] == ["AAA", "BBB"]
    assert "AAA: downloaded 3130 rows, 2010-01-04 to 2021-12-31" in result.output
    assert "survivorship" in result.output
    again = run(cli_env, "fetch", "AAA")
    assert "already cached" in again.output and len(downloader.calls) == 2
    refreshed = run(cli_env, "fetch", "AAA", "--refresh")
    assert refreshed.exit_code == 0 and len(downloader.calls) == 3
    assert run(cli_env, "fetch", "NODATA").exit_code == 1
    assert run(cli_env, "fetch", "bad/ticker").exit_code == 1


def test_cli_demo_runs_every_pair(cli_env: Project) -> None:
    result = run(cli_env, "demo")
    assert result.exit_code == 0, result.output
    out = result.output
    for pair in ("V/MA [case_study]", "KO/PEP [case_study]", "XOM/CVX [case_study]",
                 "HD/LOW [case_study]", "EWA/EWC [case_study]", "V/XOM [control]",
                 "SYNTH_A/SYNTH_B [synthetic]"):
        assert pair in out
    assert "SYNTHETIC" in out and "CONTROL" in out and "CASE STUDY" in out
    trials = TrialLog(cli_env.trials_path).read()
    assert [t.label for t in trials] == ["case_study"] * 5 + ["control", "synthetic"]


def _analyse_json(project: Project) -> dict[str, object]:
    result = run(project, "analyse", "AAA", "BBB", "--json", "--offline")
    assert result.exit_code == 0, result.output
    (payload,) = json.loads(result.output)
    return payload


def _perturb(frame: pd.DataFrame, first_row: pd.Timestamp, seed: int) -> pd.DataFrame:
    """Change everything from `first_row` on: prices, payouts, a split, NaN, gaps."""
    out = frame.copy()
    later = out.index.tz_localize(None) >= first_row
    n = int(later.sum())
    rng = np.random.default_rng(seed)
    for col in ("Open", "High", "Low", "Close", "Adj Close"):
        out.loc[later, col] = out.loc[later, col].to_numpy() * rng.uniform(0.2, 5.0, n)
    out.loc[later, "Dividends"] = rng.uniform(0.0, 30.0, n)
    position = int(np.argmax(later))
    out.iloc[position + 5, out.columns.get_loc("Stock Splits")] = 3.0
    out.iloc[position + 7, out.columns.get_loc("Close")] = np.nan
    return out.drop(out.index[[position + 2, position + 40]])


def test_cli_analyse_ignores_cached_rows_at_or_after_asof(
    cli_env: Project, downloader: FakeDownloader
) -> None:
    """Phase 2 gate, end to end: later rows in the cache never change the output.

    Every snapshot (both legs and the reference calendar) is replaced by one
    that agrees before the as-of date 2018-01-01 and differs from that date on:
    other prices, large payouts, a split, a NaN close and missing days. The
    analysis output must be identical. The row dated exactly 2018-01-01 exists
    in this business-day calendar and is among the changed rows.
    """
    assert (CALENDAR.tz_localize(None) == ASOF).any()
    assert run(cli_env, "fetch", "AAA", "BBB", "SPY").exit_code == 0
    before = _analyse_json(cli_env)

    for i, ticker in enumerate(("AAA", "BBB", "SPY")):
        downloader.frames[ticker] = _perturb(downloader.frames[ticker], ASOF, seed=i)
    assert run(cli_env, "fetch", "AAA", "BBB", "SPY", "--refresh").exit_code == 0
    after = _analyse_json(cli_env)

    assert after["result"] == before["result"]
    assert after["result"]["stats"]["nobs"] == N_FORMATION
    for ticker in ("AAA", "BBB", "SPY"):  # the new snapshots really were used
        assert (after["record"]["snapshot_ids"][ticker]
                != before["record"]["snapshot_ids"][ticker])


def test_the_look_ahead_test_can_fail(
    cli_env: Project, downloader: FakeDownloader
) -> None:
    """The same change one row earlier (the last row before asof) is detected."""
    assert run(cli_env, "fetch", "AAA", "BBB", "SPY").exit_code == 0
    before = _analyse_json(cli_env)
    frame = downloader.frames["AAA"].copy()
    last_before = int((CALENDAR.tz_localize(None) < ASOF).sum()) - 1
    frame.iloc[last_before, frame.columns.get_loc("Close")] *= 1.05
    downloader.frames["AAA"] = frame
    assert run(cli_env, "fetch", "AAA", "--refresh").exit_code == 0
    after = _analyse_json(cli_env)
    assert after["result"]["stats"] != before["result"]["stats"]

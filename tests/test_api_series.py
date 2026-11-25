"""Tests for the dashboard's equity and drawdown series."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fake_results import make_results

from statarb_agent.api.series import span_series
from statarb_agent.backtest.runs import read_manifest, read_table


def ledger(ret: list[float], gross: list[float] | None = None, *, tz: str | None = None):
    idx = pd.bdate_range("2020-01-06", periods=len(ret), tz=tz, name="date")
    return pd.DataFrame({"ret": ret, "gross_ret": ret if gross is None else gross}, index=idx)


def test_hand_worked_equity_and_drawdown() -> None:
    # equity 1.1, 0.9, 0.95; running peak 1.1 from the first row on
    s = span_series(ledger([0.1, -0.2, 0.05], [0.1, -0.1, 0.1]), "2020-01-06", "2020-01-08")
    np.testing.assert_allclose(s.equity, [1.1, 0.9, 0.95])
    np.testing.assert_allclose(s.gross_equity, [1.1, 1.0, 1.1])
    np.testing.assert_allclose(s.drawdown, [0.0, 0.2 / 1.1, 0.15 / 1.1])
    assert list(s.dates.strftime("%Y-%m-%d")) == ["2020-01-06", "2020-01-07", "2020-01-08"]


def test_a_loss_on_the_first_day_is_a_drawdown_from_the_capital() -> None:
    s = span_series(ledger([-0.1, 0.05]), "2020-01-06", "2020-01-07")
    np.testing.assert_allclose(s.drawdown, [0.1, 0.05])


def test_span_bounds_are_inclusive_and_the_span_restarts_from_the_capital() -> None:
    daily = ledger([0.5, 0.1, -0.1, 0.2, 0.3], tz="America/New_York")
    s = span_series(daily, "2020-01-07", "2020-01-09")
    assert list(s.dates.strftime("%Y-%m-%d")) == ["2020-01-07", "2020-01-08", "2020-01-09"]
    # the 0.5 before the span is not carried in
    np.testing.assert_allclose(s.equity, [1.1, 1.0, 1.2])
    np.testing.assert_allclose(s.drawdown, [0.0, 0.1 / 1.1, 0.0])


def test_drawdown_is_undefined_once_the_capital_is_lost() -> None:
    s = span_series(ledger([0.1, -1.2, 0.5]), "2020-01-06", "2020-01-08")
    np.testing.assert_allclose(s.equity, [1.1, -0.1, 0.4])
    assert s.drawdown[0] == 0.0 and np.isnan(s.drawdown[1:]).all()


def test_missing_column_or_empty_span_is_refused() -> None:
    with pytest.raises(ValueError, match="gross_ret"):
        span_series(ledger([0.1]).drop(columns="gross_ret"), "2020-01-06", "2020-01-06")
    with pytest.raises(ValueError, match="no ledger rows"):
        span_series(ledger([0.1]), "2021-01-01", "2021-02-01")


def test_matches_the_stored_metrics_of_a_real_engine_run(tmp_path: Path) -> None:
    """Largest drawdown and final equity equal the run's stored span metrics."""
    results = make_results(tmp_path)
    run_id = results.pair_run.run_id
    store = results.runner.project.runs_dir
    man = read_manifest(store, run_id)
    daily = read_table(store, run_id, "daily")
    for span in ("full", "formation", "validation"):
        metrics = man["metrics"][span]
        s = span_series(daily, metrics["start"], metrics["end"])
        assert len(s.dates) == metrics["n_days"]
        assert np.nanmax(s.drawdown) == pytest.approx(metrics["max_drawdown"], abs=1e-12)
        assert s.equity[-1] - 1.0 == pytest.approx(metrics["total_return"], abs=1e-12)

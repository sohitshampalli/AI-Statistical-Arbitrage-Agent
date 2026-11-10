"""Tests for pair_stats: it gathers the tested estimators and adds no look-ahead."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from statarb_agent.data.synthetic import simulate_cointegrated_pair
from statarb_agent.stats.cointegration import engle_granger
from statarb_agent.stats.hedge_ratio import ols_hedge_ratio, spread
from statarb_agent.stats.mean_reversion import fit_ar1
from statarb_agent.stats.pair import pair_stats
from statarb_agent.stats.unit_root import adf_test

SEED = 7
N_OBS = 900
CUT = 700


@pytest.fixture(scope="module")
def pair() -> pd.DataFrame:
    return simulate_cointegrated_pair(seed=SEED, n_obs=N_OBS)


def test_matches_the_individual_estimators(pair: pd.DataFrame) -> None:
    asof = pair.index[CUT]
    a, b = pair["log_a"], pair["log_b"]
    stats = pair_stats(a, b, asof, label_a="AAA", label_b="BBB")
    hedge = ols_hedge_ratio(a, b, asof)
    assert stats.hedge == hedge
    assert stats.nobs == CUT
    assert stats.first_obs == str(pair.index[0].date())
    assert stats.last_obs == str(pair.index[CUT - 1].date())
    assert stats.asof == str(asof.date()) and stats.start is None
    assert stats.adf_level_a == adf_test(a, asof)
    assert stats.adf_level_b == adf_test(b, asof)
    assert stats.adf_return_a == adf_test(a.diff().iloc[1:], asof)
    eg = engle_granger(a.rename("AAA"), b.rename("BBB"), asof)
    assert stats.engle_granger == eg
    assert eg.a_on_b.dependent == "AAA" and eg.b_on_a.dependent == "BBB"
    resid = spread(a.iloc[:CUT], b.iloc[:CUT], hedge)
    assert stats.spread_ar1 == fit_ar1(resid, asof)
    assert stats.spread_sd == pytest.approx(float(resid.std(ddof=1)), rel=1e-12)


def test_known_answer_on_the_synthetic_pair(pair: pd.DataFrame) -> None:
    """True beta 1.5, alpha 0.3, half-life 10; returns are stationary.

    Bounds follow the Phase 1 tests: beta error under 0.05 at long lengths and
    half-life relative error under 0.35. Measured here (seed 7, 700 rows):
    beta 1.4965, half-life 8.98.
    """
    stats = pair_stats(pair["log_a"], pair["log_b"], pair.index[CUT])
    assert abs(stats.hedge.beta - 1.5) < 0.05
    assert stats.spread_ar1.mean_reverting
    assert abs(stats.spread_ar1.half_life - 10.0) / 10.0 < 0.35
    assert stats.adf_return_a.pvalue < 0.01 and stats.adf_return_b.pvalue < 0.01
    assert stats.engle_granger.a_on_b.pvalue < 0.01
    assert stats.engle_granger.b_on_a.pvalue < 0.01


def test_rows_at_or_after_asof_change_nothing(pair: pd.DataFrame) -> None:
    """Look-ahead test: values, NaN and infinity from asof onward are never read."""
    asof = pair.index[CUT]
    before = pair_stats(pair["log_a"], pair["log_b"], asof)
    changed = pair.copy()
    rng = np.random.default_rng(1)
    changed.iloc[CUT:, 0] = rng.standard_normal(N_OBS - CUT) * 50.0  # includes asof row
    changed.iloc[CUT:, 1] = np.nan
    changed.iloc[CUT + 3, 1] = np.inf
    after = pair_stats(changed["log_a"], changed["log_b"], asof)
    assert after == before


def test_start_bounds_the_window(pair: pd.DataFrame) -> None:
    asof, start = pair.index[CUT], pair.index[100]
    stats = pair_stats(pair["log_a"], pair["log_b"], asof, start=start)
    assert stats.nobs == CUT - 100 and stats.first_obs == str(start.date())
    assert stats.start == str(start.date())
    direct = pair_stats(pair["log_a"].iloc[100:], pair["log_b"].iloc[100:], asof)
    assert stats.hedge == direct.hedge and stats.spread_ar1 == direct.spread_ar1
    # rows before start do not matter either
    changed = pair.copy()
    changed.iloc[:100, :2] = 1.0
    again = pair_stats(changed["log_a"], changed["log_b"], asof, start=start)
    assert again == stats


def test_mismatched_dates_and_short_windows_raise(pair: pd.DataFrame) -> None:
    asof = pair.index[CUT]
    with pytest.raises(ValueError, match="different dates"):
        pair_stats(pair["log_a"], pair["log_b"].drop(pair.index[10]), asof)
    with pytest.raises(ValueError, match="at least 60 rows"):
        pair_stats(pair["log_a"], pair["log_b"], pair.index[30])


def test_to_dict_is_json_ready(pair: pd.DataFrame) -> None:
    stats = pair_stats(pair["log_a"], pair["log_b"], pair.index[CUT])
    data = stats.to_dict()
    text = json.dumps(data, allow_nan=False)
    back = json.loads(text)
    assert back["hedge"]["beta"] == stats.hedge.beta
    assert back["hedge"]["last_obs"] == stats.last_obs
    assert back["engle_granger"]["a_on_b"]["pvalue"] == stats.engle_granger.a_on_b.pvalue
    assert back["spread_ar1"]["half_life"] == stats.spread_ar1.half_life

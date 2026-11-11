"""Tests for ols_hedge_ratio and spread on synthetic data with a known answer.

Beta tolerance: abs(beta_hat - beta) < 0.05 at T = 2520 on one fixed seed. In the
pre-commit Monte Carlo (400 seeds, default parameters) the SD of beta_hat - beta
was 0.0094 and the worst case 0.035. OLS beta is superconsistent (error shrinks
like 1 / T) and not normally distributed, so the bound is set from the observed
worst case with headroom, not as a multiple of an SD.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from statarb_agent.data.synthetic import simulate_cointegrated_pair
from statarb_agent.stats.hedge_ratio import (
    HedgeRatio,
    ols_hedge_ratio,
    ols_residual_sd,
    rolling_ols_hedge,
    spread,
)

SEED = 7
BETA = 1.5
ALPHA = 0.3
BETA_TOL = 0.05


@pytest.fixture(scope="module")
def pair() -> pd.DataFrame:
    return simulate_cointegrated_pair(seed=SEED, beta=BETA, alpha=ALPHA)


def test_beta_recovery(pair: pd.DataFrame) -> None:
    asof = pair.index[-1] + pd.offsets.BDay(1)
    hedge = ols_hedge_ratio(pair["log_a"], pair["log_b"], asof)
    assert hedge.nobs == 2520
    assert abs(hedge.beta - BETA) < BETA_TOL


def test_exact_recovery_without_spread() -> None:
    df = simulate_cointegrated_pair(
        seed=SEED, n_obs=500, beta=0.7, alpha=-2.0, spread_sd=0.0
    )
    hedge = ols_hedge_ratio(df["log_a"], df["log_b"], "2100-01-01")
    assert hedge.beta == pytest.approx(0.7, abs=1e-10)
    assert hedge.alpha == pytest.approx(-2.0, abs=1e-9)


def test_matches_statsmodels_on_rows_before_asof(pair: pd.DataFrame) -> None:
    cut = 1200
    hedge = ols_hedge_ratio(pair["log_a"], pair["log_b"], pair.index[cut])
    x = pair["log_b"].to_numpy()[:cut]
    y = pair["log_a"].to_numpy()[:cut]
    ref = sm.OLS(y, sm.add_constant(x)).fit().params
    assert hedge.alpha == float(ref[0])
    assert hedge.beta == float(ref[1])


def test_uses_only_rows_before_asof(pair: pd.DataFrame) -> None:
    cut = 1200
    asof = pair.index[cut]
    hedge = ols_hedge_ratio(pair["log_a"], pair["log_b"], asof)
    assert hedge.nobs == cut
    assert hedge.last_obs == pair.index[cut - 1]
    assert hedge.last_obs < asof


def test_future_rows_do_not_change_result(pair: pd.DataFrame) -> None:
    cut = 1200
    asof = pair.index[cut]
    before = ols_hedge_ratio(pair["log_a"], pair["log_b"], asof)
    rng = np.random.default_rng(99)
    a = pair["log_a"].copy()
    b = pair["log_b"].copy()
    a.iloc[cut:] = rng.standard_normal(len(a) - cut) * 50.0  # includes the asof row
    b.iloc[cut:] = -b.iloc[cut:] * 7.0
    b = b.drop(b.index[cut + 5])  # a date mismatch after asof must not matter
    assert ols_hedge_ratio(a, b, asof) == before


def test_result_has_no_standard_error() -> None:
    names = {f.name for f in dataclasses.fields(HedgeRatio)}
    assert names == {"alpha", "beta", "nobs", "last_obs"}


def test_mismatched_dates_before_asof_raise(pair: pd.DataFrame) -> None:
    b = pair["log_b"].drop(pair.index[100])
    with pytest.raises(ValueError):
        ols_hedge_ratio(pair["log_a"], b, pair.index[1200])


def test_constant_log_b_raises() -> None:
    idx = pd.bdate_range("2000-01-03", periods=50)
    a = pd.Series(np.linspace(0.0, 1.0, 50), index=idx)
    b = pd.Series(np.full(50, 4.6), index=idx)
    with pytest.raises(ValueError):
        ols_hedge_ratio(a, b, "2100-01-01")


def test_too_few_rows_raises(pair: pd.DataFrame) -> None:
    with pytest.raises(ValueError):
        ols_hedge_ratio(pair["log_a"], pair["log_b"], pair.index[5])


def test_spread_with_true_parameters_is_true_spread(pair: pd.DataFrame) -> None:
    truth = HedgeRatio(alpha=ALPHA, beta=BETA, nobs=0, last_obs=pair.index[0])
    s = spread(pair["log_a"], pair["log_b"], truth)
    assert s.name == "spread"
    pd.testing.assert_index_equal(s.index, pair.index)
    np.testing.assert_allclose(
        s.to_numpy(), pair["spread"].to_numpy(), rtol=0, atol=1e-12
    )


def test_spread_row_t_depends_only_on_row_t(pair: pd.DataFrame) -> None:
    hedge = HedgeRatio(alpha=ALPHA, beta=BETA, nobs=0, last_obs=pair.index[0])
    base = spread(pair["log_a"], pair["log_b"], hedge).to_numpy()
    t = 1000
    a = pair["log_a"].copy()
    a.iloc[t] += 1.0
    b = pair["log_b"].copy()
    b.iloc[t] += 1.0
    for leg_a, leg_b in ((a, pair["log_b"]), (pair["log_a"], b)):
        changed = spread(leg_a, leg_b, hedge).to_numpy()
        assert np.flatnonzero(changed != base).tolist() == [t]


def test_spread_mismatched_index_raises(pair: pd.DataFrame) -> None:
    truth = HedgeRatio(alpha=ALPHA, beta=BETA, nobs=0, last_obs=pair.index[0])
    with pytest.raises(ValueError):
        spread(pair["log_a"], pair["log_b"].iloc[1:], truth)


# Rolling OLS -----------------------------------------------------------------


def test_rolling_matches_static_fit_on_each_window() -> None:
    """Known answer: each row equals ols_hedge_ratio on the window before it."""
    df = simulate_cointegrated_pair(seed=7, n_obs=400)
    a, b = df["log_a"], df["log_b"]
    window = 120
    rolling = rolling_ols_hedge(a, b, "2100-01-01", window=window)
    assert len(rolling) == 400 - window
    assert rolling.index[0] == df.index[window] and rolling.index[-1] == df.index[-1]
    assert list(rolling.columns) == ["alpha", "beta", "resid_sd"]
    for t in (window, window + 1, 250, 399):
        date = df.index[t]
        rows_a, rows_b = a.iloc[t - window : t], b.iloc[t - window : t]
        static = ols_hedge_ratio(rows_a, rows_b, date)
        assert static.nobs == window and static.last_obs == df.index[t - 1]
        assert rolling.loc[date, "alpha"] == pytest.approx(static.alpha, rel=1e-9)
        assert rolling.loc[date, "beta"] == pytest.approx(static.beta, rel=1e-9)
        assert rolling.loc[date, "resid_sd"] == pytest.approx(
            ols_residual_sd(rows_a, rows_b, static), rel=1e-9
        )


def test_rolling_exact_on_a_noiseless_line() -> None:
    idx = pd.bdate_range("2015-01-01", periods=80, name="date")
    b = pd.Series(np.linspace(1.0, 2.0, 80) ** 2, index=idx)
    a = 0.25 + 1.75 * b
    rolling = rolling_ols_hedge(a, b, "2100-01-01", window=30)
    np.testing.assert_allclose(rolling["beta"], 1.75, rtol=1e-10)
    np.testing.assert_allclose(rolling["alpha"], 0.25, atol=1e-10)
    np.testing.assert_allclose(rolling["resid_sd"], 0.0, atol=1e-12)


def test_rolling_row_t_ignores_row_t_and_later() -> None:
    """Look-ahead test: changing rows from t on leaves the estimates up to t alone.

    Row t's own fit uses rows before t only, so it must not change either.
    """
    df = simulate_cointegrated_pair(seed=7, n_obs=300)
    window, cut = 60, 200
    asof = df.index[280]
    before = rolling_ols_hedge(df["log_a"], df["log_b"], asof, window=window)
    changed = df.copy()
    rng = np.random.default_rng(3)
    changed.iloc[cut:, 0] = rng.standard_normal(300 - cut) * 10.0
    changed.iloc[cut:, 1] = rng.standard_normal(300 - cut) * 10.0
    after = rolling_ols_hedge(changed["log_a"], changed["log_b"], asof, window=window)
    kept = before.index <= df.index[cut]  # includes row `cut` itself
    pd.testing.assert_frame_equal(after.loc[kept], before.loc[kept], check_exact=True)
    assert not after.loc[~kept].equals(before.loc[~kept])
    # rows at or after asof are never read or returned
    assert before.index.max() == df.index[279]
    nan_tail = df.copy()
    nan_tail.iloc[280:, :2] = np.nan
    again = rolling_ols_hedge(nan_tail["log_a"], nan_tail["log_b"], asof, window=window)
    pd.testing.assert_frame_equal(again, before, check_exact=True)


def test_rolling_constant_window_gives_nan_not_an_error() -> None:
    idx = pd.bdate_range("2015-01-01", periods=70, name="date")
    b = pd.Series(np.r_[np.full(30, 2.0), np.linspace(2.0, 3.0, 40)], index=idx)
    a = 1.0 + 0.5 * b
    rolling = rolling_ols_hedge(a, b, "2100-01-01", window=20)
    # linspace starts at 2.0, so rows 0 to 30 are all 2.0 and the fits dated up
    # to row 31 see a constant log_b.
    constant = rolling.index <= idx[31]
    assert rolling.loc[constant].isna().all().all()
    np.testing.assert_allclose(rolling.loc[~constant, "beta"], 0.5, rtol=1e-9)


def test_rolling_argument_errors() -> None:
    df = simulate_cointegrated_pair(seed=7, n_obs=100)
    a, b = df["log_a"], df["log_b"]
    with pytest.raises(ValueError, match="at least 20"):
        rolling_ols_hedge(a, b, "2100-01-01", window=5)
    with pytest.raises(TypeError):
        rolling_ols_hedge(a, b, "2100-01-01", window=30.0)
    with pytest.raises(ValueError, match="at least 101 rows"):
        rolling_ols_hedge(a, b, "2100-01-01", window=100)
    with pytest.raises(ValueError, match="different dates"):
        rolling_ols_hedge(a, b.drop(b.index[3]), "2100-01-01", window=30)
    hedge = ols_hedge_ratio(a, b, "2100-01-01")
    with pytest.raises(ValueError, match="rows of the fit"):
        ols_residual_sd(a.iloc[:50], b.iloc[:50], hedge)

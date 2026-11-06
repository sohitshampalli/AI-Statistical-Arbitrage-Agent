"""Tests for fit_ar1 on synthetic data with a known answer.

Half-life recovery uses the in-sample pipeline of the Phase 1 gate: OLS hedge
ratio, then spread, then fit_ar1, all on the same rows, with a true half-life of
10 bars. Measured before these tests were written, through this same code:

- T = 2520, seeds 0 to 399: mean relative error -0.0328, SD 0.1064, worst
  absolute relative error 0.3085 (seed 118). Bound 0.35.
- T = 10,000, seeds 0 to 199: mean relative error -0.0069, SD 0.0503, worst
  absolute relative error 0.1537 (seed 111). Bound 0.20.

Test seeds were fixed before that measurement and lie outside both ranges.

The 0 < b < 1 rule does not detect a random walk: the downward bias of OLS b puts
it under 1 on most seeds. A random walk therefore has a long implied half-life,
not mean_reverting=False. The measured property is in
test_random_walk_half_life_is_long_or_undefined.
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from statarb_agent.data.synthetic import (
    ar1_coefficient_from_half_life,
    simulate_cointegrated_pair,
)
from statarb_agent.stats.hedge_ratio import ols_hedge_ratio, spread
from statarb_agent.stats.mean_reversion import AR1Fit, _ou_parameters, fit_ar1

ASOF = pd.Timestamp("2100-01-01")  # after every simulated date
HALF_LIFE = 10.0

SEED_LOOSE = 3000
SEED_STRICT = 3001
SEED_PHI = 3002
SEED_RANDOM_WALK = 3004

LOOSE_T = 2520
LOOSE_TOL = 0.35
STRICT_T = 10_000
STRICT_TOL = 0.20
RANDOM_WALK_HALF_LIFE_BOUND = 50.0


def _series(values: np.ndarray) -> pd.Series:
    idx = pd.bdate_range("2000-01-03", periods=len(values), name="date")
    return pd.Series(values, index=idx, name="spread")


def _noiseless_ar1(a: float, b: float, n: int, start: float) -> pd.Series:
    values = np.empty(n)
    values[0] = start
    for t in range(1, n):
        values[t] = a + b * values[t - 1]
    return _series(values)


def _half_life_relative_error(seed: int, n_obs: int) -> float:
    df = simulate_cointegrated_pair(seed=seed, n_obs=n_obs, half_life=HALF_LIFE)
    hedge = ols_hedge_ratio(df["log_a"], df["log_b"], ASOF)
    fit = fit_ar1(spread(df["log_a"], df["log_b"], hedge), ASOF)
    assert fit.mean_reverting
    assert fit.half_life is not None
    return fit.half_life / HALF_LIFE - 1.0


@pytest.fixture(scope="module")
def true_spread() -> pd.Series:
    df = simulate_cointegrated_pair(seed=SEED_PHI, half_life=HALF_LIFE)
    return df["spread"]


def test_noiseless_ar1_is_recovered_exactly() -> None:
    a, b = 0.05, 0.9
    fit = fit_ar1(_noiseless_ar1(a, b, 60, 2.0), ASOF)
    assert fit.mean_reverting
    assert fit.reason is None
    assert fit.b == pytest.approx(b, abs=1e-10)
    assert fit.a == pytest.approx(a, abs=1e-10)
    assert fit.theta == pytest.approx(-math.log(b), rel=1e-10)
    assert fit.mu == pytest.approx(a / (1 - b), rel=1e-10)
    assert fit.half_life == pytest.approx(math.log(2) / -math.log(b), rel=1e-10)
    assert fit.resid_sd < 1e-10
    assert fit.nobs == 59


def test_dt_rescales_theta_and_half_life() -> None:
    series = _noiseless_ar1(0.05, 0.9, 60, 2.0)
    daily = fit_ar1(series, ASOF)
    yearly = fit_ar1(series, ASOF, dt=1.0 / 252.0)
    assert yearly.b == daily.b
    assert yearly.theta == pytest.approx(daily.theta * 252.0, rel=1e-12)
    assert yearly.half_life == pytest.approx(daily.half_life / 252.0, rel=1e-12)


def test_random_walk_half_life_is_long_or_undefined() -> None:
    """A random walk at T = 2520 has no half-life or one above 50 bars.

    Measured on seeds 5000 to 5999 at T = 2520, denominator 1000 seeds:
    - Random walk: 0 < b < 1 on 951 seeds; implied half-life median 368.92, 5th
      percentile 119.76, minimum 64.33; under 100 bars on 21 seeds (2.1 percent);
      under 50 bars on 0 seeds. On seeds 0 to 999 the minimum was 51.0.
    - True spread, half-life 10: 0 < b < 1 on all seeds; median 9.88, 5th
      percentile 8.26, maximum 13.90.

    The bound of 50 is just below the lowest of those 2000 random-walk seeds.
    This is a one-seed test, so it has a small residual chance of failing on a
    new seed.

    The gap between the groups exists only because the true half-life is 10 and
    T is long, so a half-life cap cannot replace the cointegration test. Measured
    on the true spread, same seeds:
    - T = 2520: maximum 51.01 at half-life 30 and 54.71 at half-life 32, under
      the random-walk minimum of 64.33 here but touching the 51.0 above. At
      half-life 60, 25.8 percent of fits exceed that minimum.
    - T = 252, the formation window: the groups overlap heavily. The random-walk
      median is 38.41, with 59.9 percent of seeds under 50 bars, while true
      half-life 32 gives a median of 19.37. KO/PEP was reported at about 32 days;
      that figure is not measured in this repo.
    """
    df = simulate_cointegrated_pair(seed=SEED_RANDOM_WALK)
    fit = fit_ar1(df["log_b"], ASOF)
    assert not fit.mean_reverting or fit.half_life > RANDOM_WALK_HALF_LIFE_BOUND


def test_true_spread_half_life_is_under_the_random_walk_bound(
    true_spread: pd.Series,
) -> None:
    fit = fit_ar1(true_spread, ASOF)
    assert fit.mean_reverting
    assert fit.half_life < RANDOM_WALK_HALF_LIFE_BOUND


def test_ou_parameters_b_equal_one() -> None:
    mean_reverting, theta, mu, half_life, reason = _ou_parameters(0.1, 1.0, 1.0)
    assert mean_reverting is False
    assert theta is None and mu is None and half_life is None
    assert reason is not None and ">= 1" in reason


def test_ou_parameters_b_equal_zero() -> None:
    mean_reverting, theta, mu, half_life, reason = _ou_parameters(0.1, 0.0, 1.0)
    assert mean_reverting is False
    assert theta is None and mu is None and half_life is None
    assert reason is not None and "<= 0" in reason


def test_ou_parameters_b_one_half() -> None:
    mean_reverting, theta, mu, half_life, reason = _ou_parameters(1.0, 0.5, 1.0)
    assert mean_reverting is True
    assert theta == pytest.approx(math.log(2.0), rel=1e-15)
    assert mu == 2.0
    assert half_life == pytest.approx(1.0, rel=1e-15)
    assert reason is None


@pytest.mark.parametrize("b", [1.0000001, 1.5, 3.0])
def test_ou_parameters_b_above_one(b: float) -> None:
    result = _ou_parameters(0.1, b, 1.0)
    assert result[0] is False and result[1:4] == (None, None, None)
    assert ">= 1" in result[4]


@pytest.mark.parametrize("b", [-1e-7, -0.5, -2.0])
def test_ou_parameters_b_below_zero(b: float) -> None:
    result = _ou_parameters(0.1, b, 1.0)
    assert result[0] is False and result[1:4] == (None, None, None)
    assert "<= 0" in result[4]


@pytest.mark.parametrize("dt", [0.25, 2.0, 1.0 / 252.0])
def test_ou_parameters_dt(dt: float) -> None:
    _, theta, mu, half_life, _ = _ou_parameters(1.0, 0.5, dt)
    assert theta == pytest.approx(math.log(2.0) / dt, rel=1e-15)
    assert half_life == pytest.approx(dt, rel=1e-15)
    assert mu == 2.0  # mu does not depend on dt


def test_explosive_series_is_not_mean_reverting() -> None:
    fit = fit_ar1(_noiseless_ar1(0.0, 1.01, 60, 1.0), ASOF)
    assert fit.b == pytest.approx(1.01, abs=1e-10)
    assert not fit.mean_reverting
    assert fit.theta is None and fit.mu is None and fit.half_life is None
    assert fit.reason is not None and ">= 1" in fit.reason


def test_alternating_series_is_not_mean_reverting() -> None:
    fit = fit_ar1(_series(np.tile([1.0, -1.0], 50)), ASOF)
    assert fit.b == pytest.approx(-1.0, abs=1e-10)
    assert not fit.mean_reverting
    assert fit.theta is None and fit.mu is None and fit.half_life is None
    assert fit.reason is not None and "<= 0" in fit.reason


def test_recovers_phi_on_true_spread(true_spread: pd.Series) -> None:
    phi = ar1_coefficient_from_half_life(HALF_LIFE)
    fit = fit_ar1(true_spread, ASOF)
    assert abs(fit.b - phi) < 4 * math.sqrt((1 - phi**2) / len(true_spread))


def test_half_life_loose_at_realistic_length() -> None:
    assert abs(_half_life_relative_error(SEED_LOOSE, LOOSE_T)) < LOOSE_TOL


def test_half_life_strict_at_long_length() -> None:
    assert abs(_half_life_relative_error(SEED_STRICT, STRICT_T)) < STRICT_TOL


def test_matches_ols_on_rows_before_asof(true_spread: pd.Series) -> None:
    cut = 1500
    fit = fit_ar1(true_spread, true_spread.index[cut])
    s = true_spread.to_numpy()[:cut]
    ref = sm.OLS(s[1:], sm.add_constant(s[:-1])).fit()
    assert fit.a == float(ref.params[0])
    assert fit.b == float(ref.params[1])
    assert fit.resid_sd == math.sqrt(float(ref.mse_resid))
    assert fit.nobs == cut - 1


def test_future_rows_do_not_change_result(true_spread: pd.Series) -> None:
    cut = 1500
    asof = true_spread.index[cut]
    before = fit_ar1(true_spread, asof)
    overwritten = true_spread.copy()
    rng = np.random.default_rng(99)
    overwritten.iloc[cut:] = rng.standard_normal(len(overwritten) - cut) * 100.0
    assert overwritten.iloc[cut] != true_spread.iloc[cut]  # the asof row changed
    assert fit_ar1(overwritten, asof) == before
    overwritten.iloc[cut + 3] = np.nan  # a future NaN must not raise either
    assert fit_ar1(overwritten, asof) == before


def test_plain_python_types(true_spread: pd.Series) -> None:
    fit = fit_ar1(true_spread, ASOF)
    assert isinstance(fit, AR1Fit)
    for name in ("a", "b", "resid_sd", "theta", "mu", "half_life"):
        assert type(getattr(fit, name)) is float, name
    assert type(fit.nobs) is int
    assert type(fit.mean_reverting) is bool

    bad = fit_ar1(_series(np.tile([1.0, -1.0], 50)), ASOF)
    assert type(bad.a) is float and type(bad.b) is float
    assert type(bad.resid_sd) is float and type(bad.nobs) is int
    assert type(bad.mean_reverting) is bool and type(bad.reason) is str


def test_field_names() -> None:
    names = [f.name for f in dataclasses.fields(AR1Fit)]
    assert names == [
        "a",
        "b",
        "resid_sd",
        "nobs",
        "mean_reverting",
        "theta",
        "mu",
        "half_life",
        "reason",
    ]


def test_too_few_rows_raises(true_spread: pd.Series) -> None:
    with pytest.raises(ValueError):
        fit_ar1(true_spread, true_spread.index[10])


def test_nan_before_asof_raises(true_spread: pd.Series) -> None:
    s = true_spread.copy()
    s.iloc[5] = np.nan
    with pytest.raises(ValueError):
        fit_ar1(s, true_spread.index[100])


def test_constant_series_raises() -> None:
    with pytest.raises(ValueError, match="constant"):
        fit_ar1(_series(np.full(50, 1.5)), ASOF)


def test_constant_before_asof_raises_even_if_later_rows_vary() -> None:
    values = np.full(50, 1.5)
    values[30:] = np.arange(20.0)
    series = _series(values)
    with pytest.raises(ValueError, match="constant"):
        fit_ar1(series, series.index[30])


@pytest.mark.parametrize("dt", [0.0, -1.0, math.inf, math.nan])
def test_bad_dt_raises(true_spread: pd.Series, dt: float) -> None:
    with pytest.raises(ValueError):
        fit_ar1(true_spread, ASOF, dt=dt)

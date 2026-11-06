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
from statarb_agent.stats.hedge_ratio import HedgeRatio, ols_hedge_ratio, spread

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

"""Tests for adf_test on synthetic data with a known answer.

Fixed-seed scenario: the default simulator (beta 1.5, alpha 0.3, half-life 10,
spread_sd 0.02, sigma_b 0.015, n_obs 2520).

- Log returns are stationary, so ADF should reject at 1 percent on one fixed
  seed. The worst p-value over 400 seeds in the pre-commit Monte Carlo was 2.5e-17.
- Log prices are I(1). "ADF fails to reject" is a size property, so it is tested
  as a rejection rate across many seeds (slow test below), not on one seed.
  History: the single-seed version with SEED = 7 failed (log_b p = 0.0085, a
  1.4 percent tail draw), which is why the rate test replaced it.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
import pytest
from statsmodels.tsa.stattools import adfuller

from statarb_agent.data.synthetic import simulate_cointegrated_pair
from statarb_agent.stats.unit_root import ADFResult, adf_test

SEED = 7

# Seeds for the levels rate test, fixed before the test was first run.
LEVEL_SEEDS = range(1000, 1500)
LEVEL_ALPHA = 0.05
LEVEL_RATE_MAX = 0.10
LEVEL_RATE_MIN = 0.015


@pytest.fixture(scope="module")
def pair() -> pd.DataFrame:
    return simulate_cointegrated_pair(seed=SEED)


@pytest.fixture(scope="module")
def asof(pair: pd.DataFrame) -> pd.Timestamp:
    return pair.index[-1] + pd.offsets.BDay(1)  # use every simulated row


@pytest.mark.parametrize("col", ["log_a", "log_b"])
def test_returns_reject(pair: pd.DataFrame, asof: pd.Timestamp, col: str) -> None:
    returns = pair[col].diff().dropna()
    res = adf_test(returns, asof)
    assert res.pvalue < 0.01


@pytest.mark.slow
def test_levels_rejection_rate_across_seeds(report_line: Callable[[str], None]) -> None:
    """ADF on a pure random walk (log_b) rejects at about the nominal rate.

    Derivation of the bounds:
    - Nominal size is 5 percent at alpha = 0.05.
    - Measured before this test existed: 6.3 to 6.7 percent on 1000 seeds
      (0 to 999) at n = 2520, depending on lag selection. The test is slightly
      oversized, so the upper bound needs headroom above 5 percent.
    - With 500 seeds the binomial standard error at a true rate of 6.7 percent
      is about 1.1 percentage points, so 10 percent is about 3 standard errors
      above the measured rate. A wrongly sized test (for example wrong critical
      values or a misspecified regression) would show 20 percent or more.
    - Lower bound 1.5 percent catches a degenerate test that never rejects.

    log_a's rate is reported but not asserted: its spread adds short-run
    dynamics and it measured 7.6 percent on 1000 seeds.
    """
    asof = pd.Timestamp("2100-01-01")  # after every simulated date
    reject_b = 0
    reject_a = 0
    for seed in LEVEL_SEEDS:
        df = simulate_cointegrated_pair(seed=seed)
        reject_b += adf_test(df["log_b"], asof).pvalue < LEVEL_ALPHA
        reject_a += adf_test(df["log_a"], asof).pvalue < LEVEL_ALPHA
    n = len(LEVEL_SEEDS)
    rate_b = reject_b / n
    rate_a = reject_a / n
    report_line(
        f"ADF levels rejection rate at {LEVEL_ALPHA:.0%}, seeds "
        f"{LEVEL_SEEDS.start}-{LEVEL_SEEDS.stop - 1}: "
        f"log_b {reject_b}/{n} = {rate_b:.3f} (asserted in "
        f"[{LEVEL_RATE_MIN}, {LEVEL_RATE_MAX}]), "
        f"log_a {reject_a}/{n} = {rate_a:.3f} (not asserted)"
    )
    assert LEVEL_RATE_MIN <= rate_b <= LEVEL_RATE_MAX


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"regression": "ct", "autolag": None, "maxlag": 3},
        {"regression": "n", "autolag": "BIC", "maxlag": 10},
    ],
)
def test_matches_adfuller_exactly(pair: pd.DataFrame, kwargs: dict) -> None:
    cut = 1500
    asof = pair.index[cut]
    res = adf_test(pair["log_a"], asof, **kwargs)
    ref = adfuller(pair["log_a"].to_numpy()[:cut], result_object=True, **kwargs)
    assert res.statistic == float(ref.statistic)
    assert res.pvalue == float(ref.pvalue)
    assert res.lags == int(ref.lags)
    assert res.nobs == int(ref.nobs)
    assert res.critical_values == {k: float(v) for k, v in ref.critical_values.items()}


def test_nobs_with_fixed_lag(pair: pd.DataFrame) -> None:
    res = adf_test(pair["log_a"], pair.index[1500], autolag=None, maxlag=3)
    assert res.lags == 3
    assert res.nobs == 1500 - 3 - 1


def test_result_types_and_critical_values(
    pair: pd.DataFrame, asof: pd.Timestamp
) -> None:
    res = adf_test(pair["log_b"], asof)
    assert isinstance(res, ADFResult)
    assert type(res.statistic) is float and type(res.pvalue) is float
    assert type(res.lags) is int and type(res.nobs) is int
    assert set(res.critical_values) == {"1%", "5%", "10%"}
    assert all(type(v) is float for v in res.critical_values.values())
    cv = res.critical_values
    assert cv["1%"] < cv["5%"] < cv["10%"] < 0


def test_future_rows_do_not_change_result(pair: pd.DataFrame) -> None:
    asof = pair.index[1000]
    before = adf_test(pair["log_a"], asof)
    perturbed = pair["log_a"].copy()
    rng = np.random.default_rng(99)
    perturbed.iloc[1000:] = perturbed.iloc[1000:] * 3.0 + rng.standard_normal(1520)
    assert adf_test(perturbed, asof) == before


def test_asof_row_itself_is_excluded(pair: pd.DataFrame) -> None:
    asof = pair.index[1000]
    before = adf_test(pair["log_a"], asof)
    changed = pair["log_a"].copy()
    changed.iloc[1000] = 1e9
    assert adf_test(changed, asof) == before


def test_too_few_rows_raises(pair: pd.DataFrame) -> None:
    with pytest.raises(ValueError):
        adf_test(pair["log_a"], pair.index[10])


def test_nan_before_asof_raises(pair: pd.DataFrame) -> None:
    s = pair["log_a"].copy()
    s.iloc[5] = np.nan
    with pytest.raises(ValueError):
        adf_test(s, pair.index[100])

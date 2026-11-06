"""Tests for engle_granger on synthetic data with a known answer.

Power (cointegrated pair, fixed seed): both directions must reject at 1 percent.
Measured before this commit on seeds 0 to 999 at T = 2520 with default
parameters: worst p was 2.92e-6 for A on B and 2.93e-6 for B on A (both seed
269), and no seed reached 1e-4 in either direction. B on A is not weaker, so a
single fixed seed with p < 0.01 has over three orders of magnitude of headroom
and no power rate test is needed.

Size (independent random walks): tested as a rejection rate across seeds in a
slow test, because a single-seed "does not reject" check is a lottery.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np
import pandas as pd
import pytest
from statsmodels.tsa.stattools import coint

from statarb_agent.data.synthetic import simulate_cointegrated_pair
from statarb_agent.stats.cointegration import EngleGrangerResult, engle_granger

SEED = 7

# Seeds for the size rate test, fixed before the test was first run.
SIZE_SEEDS = range(2000, 2500)
SIZE_ALPHA = 0.05
SIZE_RATE_MAX = 0.10
SIZE_RATE_MIN = 0.015


def independent_walks(
    seed: int, n_obs: int = 2520, sigma: float = 0.015
) -> pd.DataFrame:
    """Two independent driftless random walks in logs, starting at log(100)."""
    rng = np.random.default_rng(seed)
    steps = sigma * rng.standard_normal((2, n_obs - 1))
    start = np.zeros((2, 1))
    walks = math.log(100.0) + np.concatenate([start, np.cumsum(steps, axis=1)], axis=1)
    idx = pd.bdate_range("2000-01-03", periods=n_obs, name="date")
    return pd.DataFrame({"x": walks[0], "y": walks[1]}, index=idx)


@pytest.fixture(scope="module")
def pair() -> pd.DataFrame:
    return simulate_cointegrated_pair(seed=SEED)


def test_cointegrated_pair_rejects_both_directions(pair: pd.DataFrame) -> None:
    res = engle_granger(pair["log_a"], pair["log_b"], "2100-01-01")
    assert isinstance(res, EngleGrangerResult)
    assert res.a_on_b.pvalue < 0.01
    assert res.b_on_a.pvalue < 0.01


def test_labels_and_nobs(pair: pd.DataFrame) -> None:
    res = engle_granger(pair["log_a"], pair["log_b"], pair.index[1500])
    assert (res.a_on_b.dependent, res.a_on_b.independent) == ("log_a", "log_b")
    assert (res.b_on_a.dependent, res.b_on_a.independent) == ("log_b", "log_a")
    assert res.a_on_b.nobs == res.b_on_a.nobs == 1500
    unnamed = engle_granger(
        pair["log_a"].rename(None), pair["log_b"].rename(None), pair.index[1500]
    )
    assert (unnamed.a_on_b.dependent, unnamed.a_on_b.independent) == ("A", "B")


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"trend": "ct"},
        {"autolag": None, "maxlag": 2},
        {"autolag": "bic", "maxlag": 8},
    ],
)
def test_matches_coint_exactly_both_directions(
    pair: pd.DataFrame, kwargs: dict
) -> None:
    cut = 1500
    res = engle_granger(pair["log_a"], pair["log_b"], pair.index[cut], **kwargs)
    a = pair["log_a"].to_numpy()[:cut]
    b = pair["log_b"].to_numpy()[:cut]
    for direction, (y0, y1) in ((res.a_on_b, (a, b)), (res.b_on_a, (b, a))):
        ref = coint(y0, y1, **kwargs)
        assert direction.t_stat == float(ref.coint_t)
        assert direction.pvalue == float(ref.pvalue)
        assert [direction.crit_1, direction.crit_5, direction.crit_10] == [
            float(v) for v in ref.critical_values
        ]


def test_critical_values_ordered(pair: pd.DataFrame) -> None:
    res = engle_granger(pair["log_a"], pair["log_b"], "2100-01-01")
    for d in (res.a_on_b, res.b_on_a):
        assert d.crit_1 < d.crit_5 < d.crit_10 < 0


def test_future_rows_do_not_change_result(pair: pd.DataFrame) -> None:
    cut = 1500
    asof = pair.index[cut]
    before = engle_granger(pair["log_a"], pair["log_b"], asof)
    rng = np.random.default_rng(99)
    a = pair["log_a"].copy()
    b = pair["log_b"].copy()
    a.iloc[cut:] = rng.standard_normal(len(a) - cut).cumsum()  # includes the asof row
    b.iloc[cut:] = b.iloc[cut:] * -4.0
    b = b.drop(b.index[cut + 10])  # a date mismatch after asof must not matter
    assert engle_granger(a, b, asof) == before


def test_mismatched_dates_before_asof_raise(pair: pd.DataFrame) -> None:
    with pytest.raises(ValueError):
        engle_granger(
            pair["log_a"].drop(pair.index[50]), pair["log_b"], pair.index[1500]
        )


def test_too_few_rows_raises(pair: pd.DataFrame) -> None:
    with pytest.raises(ValueError):
        engle_granger(pair["log_a"], pair["log_b"], pair.index[10])


@pytest.mark.slow
def test_size_on_independent_walks(report_line: Callable[[str], None]) -> None:
    """Each direction rejects no-cointegration at about the nominal rate.

    Derivation of the bounds:
    - Nominal size is 5 percent at alpha = 0.05, for each direction separately.
    - Measured before this test existed, on seeds 0 to 999 at n = 2520 with
      this generator: 5.5 percent (x on y) and 4.8 percent (y on x).
    - With 500 seeds the binomial standard error at a true rate of 5.5 percent
      is about 1.0 percentage point, so 10 percent is about 4.4 standard errors
      above the higher measured rate and 1.5 percent about 3.3 below the lower.
      A wrongly sized test would reject far more often than the nominal rate.
    - Lower bound 1.5 percent catches a degenerate test that never rejects.

    The rate at which either direction rejects is reported, not asserted. It
    measured 8.7 percent on seeds 0 to 999, which is why the two directions
    are reported separately and never combined by taking the smaller p-value.
    """
    asof = pd.Timestamp("2100-01-01")
    rej_xy = 0
    rej_yx = 0
    rej_either = 0
    for seed in SIZE_SEEDS:
        w = independent_walks(seed)
        res = engle_granger(w["x"], w["y"], asof)
        xy = res.a_on_b.pvalue < SIZE_ALPHA
        yx = res.b_on_a.pvalue < SIZE_ALPHA
        rej_xy += xy
        rej_yx += yx
        rej_either += xy or yx
    n = len(SIZE_SEEDS)
    rate_xy = rej_xy / n
    rate_yx = rej_yx / n
    report_line(
        f"Engle-Granger size at {SIZE_ALPHA:.0%}, independent walks, seeds "
        f"{SIZE_SEEDS.start}-{SIZE_SEEDS.stop - 1}: "
        f"x on y {rej_xy}/{n} = {rate_xy:.3f}, y on x {rej_yx}/{n} = {rate_yx:.3f} "
        f"(each asserted in [{SIZE_RATE_MIN}, {SIZE_RATE_MAX}]), "
        f"either direction {rej_either}/{n} = {rej_either / n:.3f} (not asserted)"
    )
    assert SIZE_RATE_MIN <= rate_xy <= SIZE_RATE_MAX
    assert SIZE_RATE_MIN <= rate_yx <= SIZE_RATE_MAX

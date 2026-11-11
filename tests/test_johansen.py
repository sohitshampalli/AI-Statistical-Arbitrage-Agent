"""Tests for the Johansen wrapper on simulated baskets with a known answer.

Simulated basket (data.synthetic.simulate_basket): x1 = 0.2 + 0.8 x2 + 0.5 x3 +
spread, so the cointegrating vector is (1, -0.8, -0.5); scaled to absolute sum
1 that is (0.4348, -0.3478, -0.2174).

Calibration, seeds 9000 to 9299, 300 simulations per row, constant term, one
lagged difference:

  rows   basket          trace rank 0   rank 1   rank 2 or 3
  2013   independent        90.3%        8.7%       1.0%
  2013   cointegrated        0.0%       91.7%       8.3%
   252   independent        89.3%        7.7%       3.0%
   252   cointegrated       74.3%       21.0%       4.7%

So the trace test rejects "no relation" on about 10 percent of independent
baskets at a nominal 5 percent, at both lengths, and at 252 rows it finds a true
relation with half-life 10 only about a quarter of the time. Largest absolute
error of the scaled weights on cointegrated baskets: mean 0.0049 and maximum
0.0184 at 2013 rows; mean 0.088 and maximum 0.995 at 252 rows.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
import pytest

from statarb_agent.data.synthetic import simulate_basket
from statarb_agent.stats.johansen import johansen_test, normalise_weights

ASOF = "2100-01-01"
TRUE_WEIGHTS = np.array([1.0, -0.8, -0.5]) / 2.3
SLOW_SEEDS = range(9300, 9500)


def test_known_cointegrating_vector_is_recovered() -> None:
    """Seed 9500, 2013 rows. Weight error below 0.03 (calibration maximum 0.0184);
    rank at least 1 (every calibration seed)."""
    basket = simulate_basket(seed=9500, n_obs=2013)
    res = johansen_test(basket, ASOF)
    assert res.labels == ("x1", "x2", "x3") and res.nobs == 2013
    assert (res.det_order, res.k_ar_diff) == (0, 1)
    assert res.trace_stats[0] > res.trace_crit_95[0]
    assert res.max_eig_stats[0] > res.max_eig_crit_95[0]
    assert res.rank_trace >= 1 and res.rank_max_eig >= 1
    weights = np.array(res.weights)
    assert np.abs(weights).sum() == pytest.approx(1.0) and weights[0] > 0
    assert np.abs(weights - TRUE_WEIGHTS).max() < 0.03
    assert list(res.eigenvalues) == sorted(res.eigenvalues, reverse=True)
    assert len(res.trace_stats) == len(res.trace_crit_95) == 3


def test_critical_values_are_the_five_percent_column() -> None:
    """Three series, constant term: 29.7961, 15.4943, 3.8415 (trace) and
    21.1314, 14.2639, 3.8415 (maximum eigenvalue), as statsmodels 0.15.0
    tabulates them."""
    res = johansen_test(simulate_basket(seed=1, n_obs=300), ASOF)
    assert res.trace_crit_95 == (29.7961, 15.4943, 3.8415)
    assert res.max_eig_crit_95 == (21.1314, 14.2639, 3.8415)


def test_rank_is_sequential() -> None:
    """The rank stops at the first null not rejected, even if a later one would be."""
    res = johansen_test(simulate_basket(seed=9500, n_obs=2013), ASOF)
    expected = 0
    for stat, crit in zip(res.trace_stats, res.trace_crit_95, strict=True):
        if stat <= crit:
            break
        expected += 1
    assert res.rank_trace == expected


def test_rows_at_or_after_asof_change_nothing() -> None:
    """Look-ahead test."""
    basket = simulate_basket(seed=3, n_obs=500)
    asof = basket.index[400]
    before = johansen_test(basket, asof)
    assert before.nobs == 400
    changed = basket.copy()
    rng = np.random.default_rng(0)
    changed.iloc[400:] = rng.standard_normal((100, 3)) * 20.0  # includes the asof row
    changed.iloc[450, 1] = np.nan
    changed.iloc[460, 2] = np.inf
    assert johansen_test(changed, asof) == before


def test_normalise_weights() -> None:
    np.testing.assert_allclose(normalise_weights([2.0, -1.0, -1.0]), [0.5, -0.25, -0.25])
    np.testing.assert_allclose(normalise_weights([-2.0, 1.0, 1.0]), [0.5, -0.25, -0.25])
    np.testing.assert_allclose(normalise_weights([0.0, -3.0, 1.0]), [0.0, -0.75, 0.25])
    with pytest.raises(ValueError):
        normalise_weights([0.0, 0.0])
    with pytest.raises(ValueError):
        normalise_weights([np.nan, 1.0])


def test_argument_errors() -> None:
    basket = simulate_basket(seed=1, n_obs=300)
    with pytest.raises(ValueError, match="two columns"):
        johansen_test(basket[["x1"]], ASOF)
    with pytest.raises(ValueError, match="two columns"):
        johansen_test(basket["x1"], ASOF)
    with pytest.raises(ValueError, match="det_order"):
        johansen_test(basket, ASOF, det_order=2)
    with pytest.raises(ValueError, match="k_ar_diff"):
        johansen_test(basket, ASOF, k_ar_diff=-1)
    with pytest.raises(ValueError, match="at least 60 rows"):
        johansen_test(basket, basket.index[30])
    holed = basket.copy()
    holed.iloc[10, 0] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        johansen_test(holed, ASOF)


def test_simulated_basket_properties() -> None:
    """The simulator does what its docstring says."""
    basket = simulate_basket(seed=5, n_obs=400)
    again = simulate_basket(seed=5, n_obs=400)
    pd.testing.assert_frame_equal(basket, again, check_exact=True)
    no_spread = simulate_basket(seed=5, n_obs=400, spread_sd=0.0)
    np.testing.assert_allclose(
        no_spread["x1"], 0.2 + 0.8 * no_spread["x2"] + 0.5 * no_spread["x3"], rtol=1e-12
    )
    independent = simulate_basket(seed=5, n_obs=400, cointegrated=False)
    pd.testing.assert_series_equal(independent["x2"], basket["x2"], check_exact=True)
    assert not independent["x1"].equals(basket["x1"])
    with pytest.raises(ValueError):
        simulate_basket(seed=-1)


@pytest.mark.slow
def test_rank_rates_across_seeds(report_line: Callable[[str], None]) -> None:
    """Seeds 9300 to 9499 at 2013 rows. Bounds from the calibration above:

    - independent baskets: rank 0 on at least 83.5 percent (calibration 90.3
      percent, standard error 1.7 points, so 4 standard errors below);
    - cointegrated baskets: rank at least 1 on at least 97 percent (calibration
      100 percent) and mean weight error below 0.008 (calibration 0.0049).
    """
    independent = [
        johansen_test(simulate_basket(seed=s, n_obs=2013, cointegrated=False), ASOF)
        for s in SLOW_SEEDS
    ]
    cointegrated = [
        johansen_test(simulate_basket(seed=s, n_obs=2013), ASOF) for s in SLOW_SEEDS
    ]
    rank0 = float(np.mean([r.rank_trace == 0 for r in independent]))
    found = float(np.mean([r.rank_trace >= 1 for r in cointegrated]))
    error = float(np.mean(
        [np.abs(np.array(r.weights) - TRUE_WEIGHTS).max() for r in cointegrated]
    ))
    report_line(
        f"Johansen trace test at 2013 rows, seeds 9300-9499: rank 0 on {rank0:.1%} of "
        f"independent baskets; rank >= 1 on {found:.1%} of cointegrated baskets, mean "
        f"weight error {error:.4f}"
    )
    assert rank0 >= 0.835
    assert found >= 0.97
    assert error < 0.008

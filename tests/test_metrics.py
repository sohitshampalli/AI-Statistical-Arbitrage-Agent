"""Tests for the metrics, each against a number worked out by hand.

The normal distribution in the expected values comes from the standard
library (statistics.NormalDist), not from scipy, which the code under test
uses, so the two are independent.
"""

from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pytest

from statarb_agent.backtest import metrics as m

PHI = NormalDist()
R = [0.01, -0.02, 0.03, 0.00]  # mean 0.005; deviations 0.005, -0.025, 0.025, -0.005
SD = math.sqrt(0.0013 / 3)  # sum of squared deviations 0.0013, ddof 1


def test_return_volatility_and_sharpe() -> None:
    assert m.annualised_return(R) == pytest.approx(0.005 * 252)
    assert m.annualised_volatility(R) == pytest.approx(SD * math.sqrt(252))
    assert m.sharpe_per_period(R) == pytest.approx(0.005 / SD)
    assert m.sharpe_ratio(R) == pytest.approx(0.005 / SD * math.sqrt(252))
    assert m.sharpe_ratio(R, periods=12) == pytest.approx(0.005 / SD * math.sqrt(12))


def test_sharpe_is_undefined_without_variation() -> None:
    assert math.isnan(m.sharpe_ratio([0.0, 0.0, 0.0]))
    assert math.isnan(m.sharpe_ratio([0.01]))
    assert math.isnan(m.sharpe_per_period([]))
    assert math.isnan(m.annualised_return([]))
    assert math.isnan(m.annualised_volatility([0.01]))


def test_sortino() -> None:
    # only -0.02 is below zero: downside deviation sqrt(0.0004 / 4) = 0.01
    assert m.sortino_ratio(R) == pytest.approx(0.005 / 0.01 * math.sqrt(252))
    assert math.isnan(m.sortino_ratio([0.01, 0.02, 0.0]))


def test_max_drawdown_and_calmar() -> None:
    equity = [100.0, 110.0, 99.0, 104.5, 120.0, 108.0]
    # peak 110 -> 99 is 10 percent; peak 120 -> 108 is 10 percent; the first wins ties
    assert m.max_drawdown(equity) == pytest.approx(0.10)
    assert m.max_drawdown([100.0, 101.0, 102.0]) == 0.0
    assert m.max_drawdown([100.0, 50.0, 75.0, 25.0]) == pytest.approx(0.75)
    returns = [0.10, -0.11, 0.055, 0.155, -0.12]
    assert m.calmar_ratio(returns, equity) == pytest.approx(
        np.mean(returns) * 252 / 0.10
    )
    assert math.isnan(m.calmar_ratio([0.01, 0.01], [100.0, 101.0, 102.0]))
    with pytest.raises(ValueError, match="positive"):
        m.max_drawdown([100.0, 0.0])
    assert math.isnan(m.max_drawdown([]))


def test_trade_metrics() -> None:
    assert m.hit_rate([5.0, -1.0, 0.0, 2.0]) == 0.5  # a zero is not a hit
    assert math.isnan(m.hit_rate([]))
    assert m.average_holding_period([3, 5, 10]) == 6.0
    assert math.isnan(m.average_holding_period([]))


def test_turnover() -> None:
    # 504 days, capital 100: open 50 + 50, close 55 + 45 -> 200 traded over 2 years
    traded = np.zeros(504)
    traded[10], traded[30] = 100.0, 100.0
    assert m.annual_turnover(traded, 100.0) == pytest.approx(1.0)
    assert math.isnan(m.annual_turnover([], 100.0))
    assert math.isnan(m.annual_turnover([1.0], 0.0))


def test_cost_drag() -> None:
    gross = [0.010, 0.000, 0.020]
    net = [0.009, 0.000, 0.018]  # 0.003 lost over 3 days
    assert m.cost_drag(gross, net) == pytest.approx(0.001 * 252)
    with pytest.raises(ValueError):
        m.cost_drag([0.1], [0.1, 0.2])


def test_beta_to_benchmark() -> None:
    bench = np.array([0.01, -0.02, 0.015, 0.0, -0.005])
    assert m.beta_to_benchmark(0.5 * bench + 0.001, bench) == pytest.approx(0.5)
    assert m.beta_to_benchmark(-2.0 * bench, bench) == pytest.approx(-2.0)
    # hand case: r = [1, 2, 3], b = [1, 2, 4]: cov = 1.5, var(b) = 7/3
    assert m.beta_to_benchmark([1.0, 2.0, 3.0], [1.0, 2.0, 4.0]) == pytest.approx(
        1.5 / (7.0 / 3.0)
    )
    assert math.isnan(m.beta_to_benchmark([0.1, 0.2], [0.0, 0.0]))
    with pytest.raises(ValueError):
        m.beta_to_benchmark([0.1], [0.1, 0.2])


def test_skewness_and_kurtosis() -> None:
    # symmetric two-point distribution: skew 0, kurtosis 1
    assert m.skewness([-1.0, 1.0, -1.0, 1.0]) == pytest.approx(0.0)
    assert m.kurtosis([-1.0, 1.0, -1.0, 1.0]) == pytest.approx(1.0)
    # [0, 0, 0, 4]: mean 1, m2 = 3, m3 = 6, m4 = 21
    assert m.skewness([0.0, 0.0, 0.0, 4.0]) == pytest.approx(6.0 / 3.0**1.5)
    assert m.kurtosis([0.0, 0.0, 0.0, 4.0]) == pytest.approx(21.0 / 9.0)
    assert math.isnan(m.skewness([1.0, 1.0]))
    draws = np.random.default_rng(0).standard_normal(200_000)
    assert abs(m.skewness(draws)) < 0.03 and abs(m.kurtosis(draws) - 3.0) < 0.06


def test_probabilistic_sharpe_ratio() -> None:
    # normal returns: variance term 1 + SR^2 / 2
    sr, n = 0.1, 101
    expected = PHI.cdf(sr * math.sqrt(100) / math.sqrt(1 + 0.5 * sr**2))
    assert m.probabilistic_sharpe_ratio(sr, n, 0.0, 3.0) == pytest.approx(expected)
    assert m.probabilistic_sharpe_ratio(0.0, n, 0.0, 3.0) == pytest.approx(0.5)
    assert m.probabilistic_sharpe_ratio(sr, n, 0.0, 3.0, benchmark_sharpe=sr) == (
        pytest.approx(0.5)
    )
    # skew -1, kurtosis 6: variance term 1 + 0.1 + 1.25 * 0.01 = 1.1125
    expected = PHI.cdf(0.1 * 10 / math.sqrt(1.1125))
    assert m.probabilistic_sharpe_ratio(sr, n, -1.0, 6.0) == pytest.approx(expected)
    # negative skew and fat tails lower the confidence in a positive Sharpe
    assert m.probabilistic_sharpe_ratio(sr, n, -1.0, 6.0) < (
        m.probabilistic_sharpe_ratio(sr, n, 0.0, 3.0)
    )
    assert math.isnan(m.probabilistic_sharpe_ratio(math.nan, n, 0.0, 3.0))
    assert math.isnan(m.probabilistic_sharpe_ratio(sr, 1, 0.0, 3.0))
    assert math.isnan(m.probabilistic_sharpe_ratio(2.0, n, 3.0, 1.0))  # term <= 0


def test_expected_max_sharpe() -> None:
    gamma = 0.5772156649015329
    n, variance = 10, 0.01
    expected = 0.1 * (
        (1 - gamma) * PHI.inv_cdf(1 - 1 / n) + gamma * PHI.inv_cdf(1 - 1 / (n * math.e))
    )
    assert m.expected_max_sharpe(n, variance) == pytest.approx(expected, rel=1e-9)
    assert 0.15 < expected < 0.16  # about 1.57 standard deviations for N = 10
    assert m.expected_max_sharpe(100, variance) > m.expected_max_sharpe(10, variance)
    assert m.expected_max_sharpe(10, 0.0) == 0.0
    assert math.isnan(m.expected_max_sharpe(1, variance))
    assert math.isnan(m.expected_max_sharpe(10, -1.0))


def exact_expected_max(n: int) -> float:
    """Exact E[max of n independent standard normals], by numerical integration.

    E[max] = integral of x * n * phi(x) * Phi(x) ** (n - 1) over the real line.
    The density and distribution come from the standard library, independent of
    the scipy.stats calls in the code under test. No random numbers are drawn.
    """
    from scipy import integrate

    def integrand(x: float) -> float:
        return x * n * PHI.pdf(x) * PHI.cdf(x) ** (n - 1)

    value, _ = integrate.quad(
        integrand, -math.inf, math.inf, epsabs=1e-12, epsrel=1e-12, limit=200
    )
    return value


# Measured on 2026-11-23 (printed by the measurement command, recorded in
# docs/STATUS.md): exact value and expected_max_sharpe(n, 1.0) minus exact.
MEASURED_GAP = {
    2: (0.564190, -0.044434),
    3: (0.846284, +0.006520),
    5: (1.162964, +0.029630),
    10: (1.538753, +0.035846),
    20: (1.867475, +0.033233),
    50: (2.249074, +0.027229),
    100: (2.507594, +0.023009),
    1000: (3.241436, +0.013686),
    10000: (3.851616, +0.009049),
}
GAP_MAX_FOR_N_AT_LEAST_3 = 0.036  # largest measured gap 0.035846, at n = 10


def test_exact_expected_max_against_closed_forms() -> None:
    """The integrator reproduces the two known closed forms:
    E[max of 2] = 1 / sqrt(pi) and E[max of 3] = 3 / (2 sqrt(pi))."""
    assert exact_expected_max(2) == pytest.approx(1 / math.sqrt(math.pi), abs=1e-9)
    assert exact_expected_max(3) == pytest.approx(1.5 / math.sqrt(math.pi), abs=1e-9)


@pytest.mark.parametrize("n", sorted(MEASURED_GAP))
def test_expected_max_formula_against_the_exact_value(n: int) -> None:
    """Deterministic check of the closed form used for the Deflated Sharpe ratio.

    The published formula (Bailey and Lopez de Prado 2014) is an approximation.
    Measured against the exact value it overstates the expected maximum for every
    n from 3 to 10000 (by 0.0065 to 0.0358, at most 2.55 percent, at n = 5),
    which raises the hurdle and makes the Deflated Sharpe ratio slightly
    conservative. At n = 2 it understates by 0.0444 (7.9 percent); a Deflated
    Sharpe ratio is never reported with fewer than 2 trials, and this project's
    counts are far above 2.

    Tolerances: the exact value and the gap are deterministic, so each is checked
    against its printed value to 1e-6 (the printed precision). For n >= 3 the gap
    must also be positive and at most 0.036, the largest measured gap rounded up.
    """
    exact = exact_expected_max(n)
    formula = m.expected_max_sharpe(n, 1.0)
    measured_exact, measured_gap = MEASURED_GAP[n]
    assert exact == pytest.approx(measured_exact, abs=1e-6)
    assert formula - exact == pytest.approx(measured_gap, abs=1e-6)
    if n >= 3:
        assert 0.0 < formula - exact <= GAP_MAX_FOR_N_AT_LEAST_3
    # the variance scales the whole formula: sd 0.1 gives a tenth
    assert m.expected_max_sharpe(n, 0.01) == pytest.approx(formula / 10.0, rel=1e-12)


def test_deflated_sharpe_ratio() -> None:
    trials = [0.05, -0.02, 0.01, 0.08, math.nan, 0.00]
    defined = np.array([0.05, -0.02, 0.01, 0.08, 0.00])
    out = m.deflated_sharpe_ratio(0.08, 500, -0.5, 4.0, trials)
    assert out.n_trials == 6 and out.n_defined == 5
    assert out.sharpe_variance == pytest.approx(defined.var(ddof=1))
    sr0 = m.expected_max_sharpe(6, defined.var(ddof=1))
    assert out.expected_max == pytest.approx(sr0)
    term = 1 + 0.5 * 0.08 + (4.0 - 1) / 4 * 0.08**2
    expected = PHI.cdf((0.08 - sr0) * math.sqrt(499) / math.sqrt(term))
    assert out.dsr == pytest.approx(expected)
    # deflating can only lower the confidence when the hurdle is positive
    assert out.dsr < m.probabilistic_sharpe_ratio(0.08, 500, -0.5, 4.0)
    more = m.deflated_sharpe_ratio(0.08, 500, -0.5, 4.0, trials * 10)
    assert more.n_trials == 60 and more.dsr < out.dsr  # more trials, lower DSR


def test_deflated_sharpe_is_undefined_with_too_few_trials() -> None:
    assert math.isnan(m.deflated_sharpe_ratio(0.1, 500, 0.0, 3.0, [0.1]).dsr)
    out = m.deflated_sharpe_ratio(0.1, 500, 0.0, 3.0, [0.1, math.nan, math.nan])
    assert out.n_trials == 3 and out.n_defined == 1 and math.isnan(out.dsr)
    with pytest.raises(ValueError):
        m.deflated_sharpe_ratio(0.1, 500, 0.0, 3.0, [[0.1, 0.2]])


def test_non_finite_inputs_raise() -> None:
    for fn in (m.sharpe_ratio, m.sortino_ratio, m.annualised_return, m.skewness):
        with pytest.raises(ValueError, match="NaN or infinity"):
            fn([0.01, math.nan])
    with pytest.raises(ValueError, match="one-dimensional"):
        m.sharpe_ratio([[0.01, 0.02]])

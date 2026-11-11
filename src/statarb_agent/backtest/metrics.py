"""Performance metrics. Pure functions on arrays; nothing here reads prices.

Conventions used everywhere in this project:

- A "return" is a daily profit divided by a fixed capital. Positions are sized
  on the initial capital and profits are not reinvested, so returns add up and
  the annualised return is the mean daily return times 252.
- An undefined metric (no variation, no trades, too few rows) is NaN, never 0.
- Sharpe ratios are quoted two ways: per period (daily mean over daily standard
  deviation, used inside the Probabilistic and Deflated Sharpe formulas) and
  annualised (the per-period value times sqrt(252)).

Probabilistic and Deflated Sharpe ratio follow Bailey and Lopez de Prado
(2014), "The deflated Sharpe ratio", Journal of Portfolio Management 40(5):

    PSR(SR*) = Phi( (SR - SR*) sqrt(T - 1) / sqrt(1 - g3 SR + (g4 - 1) / 4 SR^2) )

with SR and SR* per period, T the number of returns, g3 the skewness and g4 the
kurtosis (3 for a normal distribution) of the returns. The Deflated Sharpe
ratio is PSR(SR0), where SR0 is the Sharpe ratio one expects from the best of N
unskilled trials whose Sharpe ratios have variance V:

    SR0 = sqrt(V) ( (1 - g) Phi^-1(1 - 1/N) + g Phi^-1(1 - 1/(N e)) )

with g the Euler-Mascheroni constant. A Deflated Sharpe ratio near 1 says the
result is unlikely to be the luckiest of N tries; near 0.5 or below says it is
what luck alone would give.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.stats import norm

PERIODS_PER_YEAR = 252
NAN = float("nan")


def _array(values: object, name: str) -> np.ndarray:
    out = np.asarray(values, dtype=float)
    if out.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if not np.isfinite(out).all():
        raise ValueError(f"{name} contains NaN or infinity")
    return out


def annualised_return(returns: object, periods: int = PERIODS_PER_YEAR) -> float:
    """Mean return per period times the number of periods in a year."""
    r = _array(returns, "returns")
    return float(r.mean() * periods) if len(r) else NAN


def annualised_volatility(returns: object, periods: int = PERIODS_PER_YEAR) -> float:
    """Sample standard deviation (ddof 1) times sqrt(periods)."""
    r = _array(returns, "returns")
    return float(r.std(ddof=1) * math.sqrt(periods)) if len(r) > 1 else NAN


def sharpe_per_period(returns: object) -> float:
    """Mean over sample standard deviation (ddof 1). NaN if the deviation is 0."""
    r = _array(returns, "returns")
    if len(r) < 2:
        return NAN
    sd = float(r.std(ddof=1))
    return float(r.mean() / sd) if sd > 0.0 else NAN


def sharpe_ratio(returns: object, periods: int = PERIODS_PER_YEAR) -> float:
    """Annualised Sharpe ratio: sharpe_per_period times sqrt(periods).

    No risk-free rate is subtracted: the strategy is dollar-neutral and its
    cash earns nothing in this model.
    """
    return sharpe_per_period(returns) * math.sqrt(periods)


def sortino_ratio(returns: object, periods: int = PERIODS_PER_YEAR) -> float:
    """Annualised mean over downside deviation, with a target of zero.

    Downside deviation is sqrt(mean(min(r, 0)^2)) over all periods. NaN if no
    return is negative.
    """
    r = _array(returns, "returns")
    if len(r) < 2:
        return NAN
    downside = float(np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)))
    return float(r.mean() / downside * math.sqrt(periods)) if downside > 0.0 else NAN


def max_drawdown(equity: object) -> float:
    """Largest fall from a running peak, as a positive fraction of that peak.

    Raises:
        ValueError: If any equity value is not positive.
    """
    e = _array(equity, "equity")
    if len(e) == 0:
        return NAN
    if (e <= 0.0).any():
        raise ValueError("equity must be positive to measure a drawdown")
    peak = np.maximum.accumulate(e)
    return float(((peak - e) / peak).max())


def calmar_ratio(
    returns: object, equity: object, periods: int = PERIODS_PER_YEAR
) -> float:
    """Annualised return over maximum drawdown. NaN if there is no drawdown."""
    drawdown = max_drawdown(equity)
    if not drawdown > 0.0:
        return NAN
    return annualised_return(returns, periods) / drawdown


def hit_rate(trade_pnls: object) -> float:
    """Share of trades with a profit strictly above zero. NaN with no trades."""
    p = _array(trade_pnls, "trade_pnls")
    return float((p > 0.0).mean()) if len(p) else NAN


def average_holding_period(bars_held: object) -> float:
    """Mean number of bars a trade was held. NaN with no trades."""
    b = _array(bars_held, "bars_held")
    return float(b.mean()) if len(b) else NAN


def annual_turnover(
    traded_notional: object, capital: float, periods: int = PERIODS_PER_YEAR
) -> float:
    """Total traded notional over capital, per year.

    Every leg of every trade counts once at its traded value, so opening and
    closing a position of one unit of capital in total gives a turnover of 2.
    """
    t = _array(traded_notional, "traded_notional")
    if len(t) == 0 or not capital > 0.0:
        return NAN
    return float(t.sum() / capital * periods / len(t))


def cost_drag(
    gross_returns: object, net_returns: object, periods: int = PERIODS_PER_YEAR
) -> float:
    """Annualised return lost to costs: (mean gross - mean net) times periods."""
    g = _array(gross_returns, "gross_returns")
    n = _array(net_returns, "net_returns")
    if len(g) != len(n):
        raise ValueError("gross and net returns must be equally long")
    return float((g.mean() - n.mean()) * periods) if len(g) else NAN


def beta_to_benchmark(returns: object, benchmark_returns: object) -> float:
    """OLS slope of the strategy's returns on the benchmark's returns.

    Sample covariance over sample variance (both ddof 1). NaN if the benchmark
    does not vary or there are fewer than two rows.
    """
    r = _array(returns, "returns")
    b = _array(benchmark_returns, "benchmark_returns")
    if len(r) != len(b):
        raise ValueError("returns and benchmark returns must be equally long")
    if len(r) < 2:
        return NAN
    variance = float(b.var(ddof=1))
    if not variance > 0.0:
        return NAN
    return float(np.cov(r, b, ddof=1)[0, 1] / variance)


def skewness(returns: object) -> float:
    """Third standardised moment (population form, m3 / m2^1.5)."""
    r = _array(returns, "returns")
    if len(r) < 2:
        return NAN
    d = r - r.mean()
    m2 = float(np.mean(d**2))
    return float(np.mean(d**3) / m2**1.5) if m2 > 0.0 else NAN


def kurtosis(returns: object) -> float:
    """Fourth standardised moment (population form, m4 / m2^2; 3 for a normal)."""
    r = _array(returns, "returns")
    if len(r) < 2:
        return NAN
    d = r - r.mean()
    m2 = float(np.mean(d**2))
    return float(np.mean(d**4) / m2**2) if m2 > 0.0 else NAN


def probabilistic_sharpe_ratio(
    sharpe: float, n_obs: int, skew: float, kurt: float, benchmark_sharpe: float = 0.0
) -> float:
    """Probability that the true per-period Sharpe ratio exceeds a benchmark.

    Args:
        sharpe: Observed Sharpe ratio per period (not annualised).
        n_obs: Number of returns T.
        skew, kurt: Skewness and kurtosis of the returns (kurtosis 3 = normal).
        benchmark_sharpe: SR*, per period.

    Returns:
        PSR in [0, 1], or NaN if an input is NaN, T < 2, or the variance term
        1 - skew * SR + (kurt - 1) / 4 * SR^2 is not positive.
    """
    values = (sharpe, skew, kurt, benchmark_sharpe)
    if n_obs < 2 or not all(math.isfinite(v) for v in values):
        return NAN
    variance_term = 1.0 - skew * sharpe + (kurt - 1.0) / 4.0 * sharpe**2
    if not variance_term > 0.0:
        return NAN
    z = (sharpe - benchmark_sharpe) * math.sqrt(n_obs - 1) / math.sqrt(variance_term)
    return float(norm.cdf(z))


def expected_max_sharpe(n_trials: int, sharpe_variance: float) -> float:
    """Expected best per-period Sharpe ratio among N unskilled trials (SR0).

    NaN if N < 2 (there is no selection to correct for with one trial) or the
    variance is negative or NaN.
    """
    if n_trials < 2 or not (math.isfinite(sharpe_variance) and sharpe_variance >= 0.0):
        return NAN
    gamma = float(np.euler_gamma)
    return float(
        math.sqrt(sharpe_variance)
        * (
            (1.0 - gamma) * norm.ppf(1.0 - 1.0 / n_trials)
            + gamma * norm.ppf(1.0 - 1.0 / (n_trials * math.e))
        )
    )


@dataclass(frozen=True)
class DeflatedSharpe:
    """A Deflated Sharpe ratio with the numbers that went into it.

    Attributes:
        dsr: PSR against expected_max, or NaN if undefined.
        expected_max: SR0, the expected best per-period Sharpe among the trials.
        n_trials: Number of trials N used.
        n_defined: How many of those trials had a defined Sharpe ratio.
        sharpe_variance: Variance (ddof 1) of the defined trial Sharpe ratios.
    """

    dsr: float
    expected_max: float
    n_trials: int
    n_defined: int
    sharpe_variance: float


def deflated_sharpe_ratio(
    sharpe: float, n_obs: int, skew: float, kurt: float, trial_sharpes: object
) -> DeflatedSharpe:
    """Deflated Sharpe ratio of one result given every trial's Sharpe ratio.

    Args:
        sharpe: Per-period Sharpe ratio of the result being judged.
        n_obs, skew, kurt: Length, skewness and kurtosis of its returns.
        trial_sharpes: Per-period Sharpe ratio of every trial, including this
            one. NaN entries (a trial that never traded) count towards N but
            not towards the variance.

    Returns:
        DeflatedSharpe. dsr is NaN with fewer than 2 trials or fewer than 2
        defined trial Sharpe ratios.
    """
    trials = np.asarray(trial_sharpes, dtype=float)
    if trials.ndim != 1:
        raise ValueError("trial_sharpes must be one-dimensional")
    defined = trials[np.isfinite(trials)]
    n_trials = len(trials)
    variance = float(defined.var(ddof=1)) if len(defined) >= 2 else NAN
    sr0 = expected_max_sharpe(n_trials, variance)
    dsr = probabilistic_sharpe_ratio(sharpe, n_obs, skew, kurt, sr0)
    return DeflatedSharpe(
        dsr=dsr, expected_max=sr0, n_trials=n_trials, n_defined=len(defined),
        sharpe_variance=variance,
    )

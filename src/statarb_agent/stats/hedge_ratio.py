"""Static OLS hedge ratio and the implied spread.

Model: log_a = alpha + beta * log_b + eps, fitted by OLS on the rows strictly
before an as-of date. No standard error is reported: the residuals are serially
correlated (they are the spread), so the textbook OLS standard error is invalid.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

from statarb_agent.stats._asof import paired_rows_before

HEDGE_MIN_OBS = 20


@dataclass(frozen=True)
class HedgeRatio:
    """OLS fit of log_a on a constant and log_b.

    Attributes:
        alpha: Intercept.
        beta: Hedge ratio (units of log_b per unit of log_a).
        nobs: Rows used, all dated strictly before the as-of date.
        last_obs: Date of the last row used.
    """

    alpha: float
    beta: float
    nobs: int
    last_obs: pd.Timestamp


def ols_hedge_ratio(
    log_a: pd.Series,
    log_b: pd.Series,
    asof: pd.Timestamp | str,
    *,
    min_obs: int = HEDGE_MIN_OBS,
) -> HedgeRatio:
    """Fit log_a = alpha + beta * log_b by OLS on rows strictly before `asof`.

    Both legs must have identical dates before `asof`; otherwise ValueError.
    Raises ValueError if log_b is constant over the window (beta unidentified).
    """
    a, b = paired_rows_before(log_a, log_b, asof, min_obs=min_obs)
    x = b.to_numpy(dtype=float)
    if np.ptp(x) == 0.0:
        raise ValueError("log_b is constant before asof; beta is not identified")
    exog = sm.add_constant(x, prepend=True, has_constant="raise")
    res = sm.OLS(a.to_numpy(dtype=float), exog).fit()
    alpha, beta = res.params
    return HedgeRatio(
        alpha=float(alpha),
        beta=float(beta),
        nobs=len(a),
        last_obs=pd.Timestamp(a.index[-1]),
    )


def spread(log_a: pd.Series, log_b: pd.Series, hedge: HedgeRatio) -> pd.Series:
    """Return log_a - alpha - beta * log_b, row by row, with given parameters.

    Row t uses only row t of each leg, so this adds no look-ahead of its own.
    The legs must have identical indexes; otherwise ValueError.
    """
    if not log_a.index.equals(log_b.index):
        raise ValueError(
            "the two legs have different indexes; align them explicitly first"
        )
    out = log_a - hedge.alpha - hedge.beta * log_b
    out.name = "spread"
    return out

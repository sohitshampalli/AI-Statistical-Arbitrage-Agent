"""OLS hedge ratio, static and rolling, and the implied spread.

Model: log_a = alpha + beta * log_b + eps, fitted by OLS on the rows strictly
before an as-of date. No standard error is reported: the residuals are serially
correlated (they are the spread), so the textbook OLS standard error is invalid.

ols_hedge_ratio fits one window. rolling_ols_hedge fits, for every row t, the
`window` rows strictly before t, so the estimate dated t never uses row t or
anything later. The Kalman filter variant is in stats.kalman.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from numpy.lib.stride_tricks import sliding_window_view

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


def rolling_ols_hedge(
    log_a: pd.Series,
    log_b: pd.Series,
    asof: pd.Timestamp | str,
    *,
    window: int,
) -> pd.DataFrame:
    """Rolling OLS of log_a on log_b: row t is fitted on the `window` rows before t.

    For each row t with at least `window` rows before it (and t strictly before
    `asof`), fit log_a = alpha + beta * log_b on rows t - window, ..., t - 1.
    Row t itself is not in its own fit, so alpha[t] and beta[t] are forecasts
    available at the close of t - 1.

    Args:
        log_a, log_b: Log prices with identical dates before `asof`.
        asof: As-of date. Only rows strictly before it are used or returned.
        window: Rows per fit, at least HEDGE_MIN_OBS.

    Returns:
        DataFrame indexed by the dates t that have a full window before them
        (the first `window` rows are absent), with columns:
        alpha, beta: the fit on the window before t.
        resid_sd: residual standard deviation of that fit, with degrees of
            freedom window - 2.
        A window in which log_b is constant gives NaN in all three columns.

    Raises:
        ValueError: If window < HEDGE_MIN_OBS, the legs' dates differ, or there
            are not more than `window` rows before `asof`.
    """
    if isinstance(window, bool) or not isinstance(window, (int, np.integer)):
        raise TypeError(f"window must be an integer, got {window!r}")
    if window < HEDGE_MIN_OBS:
        raise ValueError(f"window must be at least {HEDGE_MIN_OBS}, got {window}")
    a, b = paired_rows_before(log_a, log_b, asof, min_obs=window + 1)
    y = a.to_numpy(dtype=float)
    x = b.to_numpy(dtype=float)
    # Row k of each view is rows k, ..., k + window - 1: the fit for row
    # k + window. The last view would be the fit for the row after the data, so
    # it is dropped.
    xw = sliding_window_view(x, window)[:-1]
    yw = sliding_window_view(y, window)[:-1]
    x_mean = xw.mean(axis=1, keepdims=True)
    y_mean = yw.mean(axis=1, keepdims=True)
    dx = xw - x_mean
    dy = yw - y_mean
    sxx = (dx * dx).sum(axis=1)
    sxy = (dx * dy).sum(axis=1)
    identified = np.ptp(xw, axis=1) > 0.0
    beta = np.full(len(xw), np.nan)
    np.divide(sxy, sxx, out=beta, where=identified)
    alpha = y_mean[:, 0] - beta * x_mean[:, 0]
    resid = dy - beta[:, None] * dx
    resid_sd = np.sqrt((resid * resid).sum(axis=1) / (window - 2))
    resid_sd[~identified] = np.nan
    return pd.DataFrame(
        {"alpha": alpha, "beta": beta, "resid_sd": resid_sd},
        index=pd.DatetimeIndex(a.index[window:], name=a.index.name),
    )


def ols_residual_sd(log_a: pd.Series, log_b: pd.Series, hedge: HedgeRatio) -> float:
    """Residual standard deviation of an OLS hedge fit on its own rows.

    `log_a` and `log_b` must be exactly the rows the fit used (hedge.nobs rows).
    Degrees of freedom are nobs - 2, the same as rolling_ols_hedge.
    """
    if len(log_a) != hedge.nobs or len(log_b) != hedge.nobs:
        raise ValueError(
            f"expected the {hedge.nobs} rows of the fit, got {len(log_a)} and "
            f"{len(log_b)}"
        )
    resid = spread(log_a, log_b, hedge).to_numpy(dtype=float)
    return float(np.sqrt((resid * resid).sum() / (hedge.nobs - 2)))

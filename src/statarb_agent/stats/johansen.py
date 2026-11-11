"""Johansen cointegration test for a basket of three or more series.

Wraps statsmodels.tsa.vector_ar.vecm.coint_johansen (statsmodels 0.15.0), which
takes (endog, det_order, k_ar_diff) and returns an object with:
- lr1 / cvt: trace statistics and their 90, 95 and 99 percent critical values,
- lr2 / cvm: maximum-eigenvalue statistics and their critical values,
- eig, evec: eigenvalues (largest first) and eigenvectors (columns).

Row i of the statistics tests the null "at most i cointegrating relations". The
rank reported here is found the usual sequential way: start at i = 0 and stop at
the first null that is not rejected at 5 percent.

The first eigenvector is the estimated cointegrating vector with the largest
eigenvalue. It is returned scaled so its absolute values sum to 1 and its first
component is positive, which makes it a set of portfolio weights on the log
prices.

statsmodels computes the eigenvalues as complex numbers with zero imaginary
part and warns when it drops that part; the warning is silenced here and the
imaginary parts are checked to be zero.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from statsmodels.tsa.vector_ar.vecm import coint_johansen

from statarb_agent.stats._asof import rows_before

JOHANSEN_MIN_OBS = 60
_CRIT_95_COLUMN = 1  # columns of cvt and cvm are 90, 95, 99 percent


@dataclass(frozen=True)
class JohansenResult:
    """Johansen test on the rows before an as-of date.

    Attributes:
        labels: Column names, in the order of the weights.
        nobs: Rows used, all dated strictly before the as-of date.
        det_order: Deterministic term (0 = constant, -1 = none, 1 = trend).
        k_ar_diff: Lagged differences in the model.
        trace_stats: Trace statistic for "at most i relations", i = 0, 1, ...
        trace_crit_95: Their 5 percent critical values.
        max_eig_stats: Maximum-eigenvalue statistics, same order.
        max_eig_crit_95: Their 5 percent critical values.
        rank_trace: Rank from the sequential trace test at 5 percent.
        rank_max_eig: Rank from the sequential maximum-eigenvalue test.
        eigenvalues: Eigenvalues, largest first.
        weights: First eigenvector, scaled to sum of absolute values 1 with a
            positive first component.
    """

    labels: tuple[str, ...]
    nobs: int
    det_order: int
    k_ar_diff: int
    trace_stats: tuple[float, ...]
    trace_crit_95: tuple[float, ...]
    max_eig_stats: tuple[float, ...]
    max_eig_crit_95: tuple[float, ...]
    rank_trace: int
    rank_max_eig: int
    eigenvalues: tuple[float, ...]
    weights: tuple[float, ...]


def _sequential_rank(stats: np.ndarray, critical: np.ndarray) -> int:
    rank = 0
    for stat, crit in zip(stats, critical, strict=True):
        if not stat > crit:
            break
        rank += 1
    return rank


def _real(values: np.ndarray, what: str) -> np.ndarray:
    values = np.asarray(values)
    if np.iscomplexobj(values):
        scale = max(1.0, float(np.abs(values).max()))
        if np.abs(values.imag).max() > 1e-9 * scale:
            raise ValueError(f"Johansen {what} have a non-zero imaginary part")
        values = values.real
    return values.astype(float)


def normalise_weights(vector: np.ndarray) -> np.ndarray:
    """Scale a vector to sum of absolute values 1 with a positive first component.

    If the first component is exactly zero the sign is left as given.

    Raises:
        ValueError: If the vector is all zeros or not finite.
    """
    w = np.asarray(vector, dtype=float)
    total = np.abs(w).sum()
    if not np.isfinite(total) or total == 0.0:
        raise ValueError("cannot normalise a zero or non-finite vector")
    w = w / total
    return -w if w[0] < 0.0 else w


def johansen_test(
    log_prices: pd.DataFrame,
    asof: pd.Timestamp | str,
    *,
    det_order: int = 0,
    k_ar_diff: int = 1,
    min_obs: int = JOHANSEN_MIN_OBS,
) -> JohansenResult:
    """Run the Johansen test on the rows of `log_prices` strictly before `asof`.

    Args:
        log_prices: One column of log prices per asset, at least two columns,
            on a DatetimeIndex.
        asof: As-of date. Only rows dated strictly before it are used.
        det_order: -1 no deterministic term, 0 constant, 1 constant and trend.
        k_ar_diff: Number of lagged differences.
        min_obs: Minimum rows required before `asof`.

    Raises:
        ValueError: On fewer than two columns, a bad det_order or k_ar_diff, or
            for any reason rows_before raises (too few rows, NaN, infinity).
    """
    if not isinstance(log_prices, pd.DataFrame) or log_prices.shape[1] < 2:
        raise ValueError("log_prices must be a DataFrame with at least two columns")
    if det_order not in (-1, 0, 1):
        raise ValueError(f"det_order must be -1, 0 or 1, got {det_order!r}")
    if isinstance(k_ar_diff, bool) or not isinstance(k_ar_diff, int) or k_ar_diff < 0:
        raise ValueError(f"k_ar_diff must be a non-negative integer, got {k_ar_diff!r}")
    past = rows_before(log_prices, asof, min_obs=min_obs)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Casting complex values to real")
        res = coint_johansen(past.to_numpy(dtype=float), det_order, k_ar_diff)
    trace = _real(res.lr1, "trace statistics")
    max_eig = _real(res.lr2, "maximum-eigenvalue statistics")
    trace_crit = np.asarray(res.cvt, dtype=float)[:, _CRIT_95_COLUMN]
    max_eig_crit = np.asarray(res.cvm, dtype=float)[:, _CRIT_95_COLUMN]
    weights = normalise_weights(_real(res.evec, "eigenvectors")[:, 0])
    return JohansenResult(
        labels=tuple(str(c) for c in past.columns),
        nobs=len(past),
        det_order=det_order,
        k_ar_diff=k_ar_diff,
        trace_stats=tuple(float(v) for v in trace),
        trace_crit_95=tuple(float(v) for v in trace_crit),
        max_eig_stats=tuple(float(v) for v in max_eig),
        max_eig_crit_95=tuple(float(v) for v in max_eig_crit),
        rank_trace=_sequential_rank(trace, trace_crit),
        rank_max_eig=_sequential_rank(max_eig, max_eig_crit),
        eigenvalues=tuple(float(v) for v in _real(res.eig, "eigenvalues")),
        weights=tuple(float(v) for v in weights),
    )

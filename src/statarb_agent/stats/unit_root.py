"""Augmented Dickey-Fuller unit root test with an as-of cutoff.

Null hypothesis: the series has a unit root. A small p-value rejects the unit root.
Wraps statsmodels.tsa.stattools.adfuller (statsmodels 0.15.0) with
result_object=True, because the tuple return is deprecated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd
from statsmodels.tsa.stattools import adfuller

from statarb_agent.stats._asof import rows_before

ADF_MIN_OBS = 20


@dataclass(frozen=True)
class ADFResult:
    """Outcome of an ADF test on the rows before an as-of date.

    Attributes:
        statistic: ADF test statistic.
        pvalue: MacKinnon approximate p-value.
        lags: Number of lagged differences used.
        nobs: Observations used in the ADF regression.
        critical_values: Critical values keyed "1%", "5%", "10%".
    """

    statistic: float
    pvalue: float
    lags: int
    nobs: int
    critical_values: dict[str, float]


def adf_test(
    series: pd.Series,
    asof: pd.Timestamp | str,
    *,
    regression: Literal["c", "ct", "ctt", "n"] = "c",
    autolag: Literal["AIC", "BIC", "t-stat"] | None = "AIC",
    maxlag: int | None = None,
    min_obs: int = ADF_MIN_OBS,
) -> ADFResult:
    """Run the ADF test on the rows of `series` strictly before `asof`.

    Args:
        series: Values with a DatetimeIndex, for example log prices or log returns.
        asof: As-of date. Only rows dated strictly before it are used.
        regression: Deterministic terms in the test regression ("c" = constant).
        autolag: Lag selection criterion, or None to use exactly `maxlag` lags.
        maxlag: Maximum lag (statsmodels default 12 * (nobs / 100) ** 0.25 if None).
        min_obs: Minimum rows required before `asof`.

    Returns:
        ADFResult with plain Python floats and ints.
    """
    past = rows_before(series, asof, min_obs=min_obs)
    res = adfuller(
        past.to_numpy(dtype=float),
        maxlag=maxlag,
        regression=regression,
        autolag=autolag,
        result_object=True,
    )
    return ADFResult(
        statistic=float(res.statistic),
        pvalue=float(res.pvalue),
        lags=int(res.lags),
        nobs=int(res.nobs),
        critical_values={k: float(v) for k, v in res.critical_values.items()},
    )

"""All formation-window statistics for one pair, computed in one call.

pair_stats runs, on the rows in [start, asof) only:

1. ADF on each log price (levels) and on each log return.
2. The static OLS hedge ratio of log_a on log_b.
3. Engle-Granger in both directions.
4. The AR(1) fit of the spread log_a - alpha - beta * log_b, which gives the
   half-life when 0 < b < 1.

It only gathers results from the tested estimators in this package; it has no
statistics of its own. Each estimator applies the as-of cutoff itself, and
pair_stats also cuts both legs first, so nothing at or after asof is read.

The spread is in sample: alpha and beta come from the same rows the AR(1) is
fitted on. That is correct for a screen on a formation window, and wrong for
trading; the backtester estimates on one window and trades on the next.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from statarb_agent.stats._asof import paired_rows_before
from statarb_agent.stats.cointegration import EngleGrangerResult, engle_granger
from statarb_agent.stats.hedge_ratio import HedgeRatio, ols_hedge_ratio, spread
from statarb_agent.stats.mean_reversion import AR1Fit, fit_ar1
from statarb_agent.stats.unit_root import ADFResult, adf_test

PAIR_MIN_OBS = 60


@dataclass(frozen=True)
class PairStats:
    """Statistics of one pair on the rows in [start, asof).

    Attributes:
        label_a, label_b: Names of the legs (tickers).
        start: First date allowed (ISO), or None for no lower bound.
        asof: As-of date (ISO). Only rows strictly before it were used.
        nobs: Rows used.
        first_obs, last_obs: First and last dates used (ISO).
        adf_level_a, adf_level_b: ADF on the log price of each leg.
        adf_return_a, adf_return_b: ADF on the log return of each leg.
        hedge: OLS fit of log_a on log_b.
        engle_granger: Both directions of the Engle-Granger test.
        spread_ar1: AR(1) fit of the in-sample spread; holds the half-life.
        spread_sd: Sample standard deviation (ddof 1) of the in-sample spread.
    """

    label_a: str
    label_b: str
    start: str | None
    asof: str
    nobs: int
    first_obs: str
    last_obs: str
    adf_level_a: ADFResult
    adf_level_b: ADFResult
    adf_return_a: ADFResult
    adf_return_b: ADFResult
    hedge: HedgeRatio
    engle_granger: EngleGrangerResult
    spread_ar1: AR1Fit
    spread_sd: float

    def to_dict(self) -> dict[str, Any]:
        """Plain JSON-ready dict (dates as ISO strings)."""
        return _plain(dataclasses.asdict(self))


def _plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return str(value.date())
    return value


def pair_stats(
    log_a: pd.Series,
    log_b: pd.Series,
    asof: pd.Timestamp | str,
    *,
    start: pd.Timestamp | str | None = None,
    label_a: str = "A",
    label_b: str = "B",
    min_obs: int = PAIR_MIN_OBS,
) -> PairStats:
    """Compute every screen statistic for a pair on rows in [start, asof).

    Args:
        log_a, log_b: Log prices with identical dates in the window (align
            them first with data.alignment.align_pair).
        asof: As-of date; only rows strictly before it are used.
        start: Optional first date of the window.
        label_a, label_b: Names used in the result.
        min_obs: Minimum rows in the window.

    Raises:
        ValueError: If the legs' dates differ in the window, there are fewer
            than min_obs rows, or for any reason an estimator raises.
    """
    cutoff = pd.Timestamp(asof)
    first = None if start is None else pd.Timestamp(start)
    if first is not None:
        log_a = log_a.loc[log_a.index >= first]
        log_b = log_b.loc[log_b.index >= first]
    a, b = paired_rows_before(log_a, log_b, cutoff, min_obs=min_obs)
    a = a.rename(label_a)
    b = b.rename(label_b)
    hedge = ols_hedge_ratio(a, b, cutoff)
    resid = spread(a, b, hedge)
    return PairStats(
        label_a=label_a,
        label_b=label_b,
        start=None if first is None else str(first.date()),
        asof=str(cutoff.date()),
        nobs=len(a),
        first_obs=str(a.index[0].date()),
        last_obs=str(a.index[-1].date()),
        adf_level_a=adf_test(a, cutoff),
        adf_level_b=adf_test(b, cutoff),
        adf_return_a=adf_test(a.diff().iloc[1:], cutoff),
        adf_return_b=adf_test(b.diff().iloc[1:], cutoff),
        hedge=hedge,
        engle_granger=engle_granger(a, b, cutoff),
        spread_ar1=fit_ar1(resid, cutoff),
        spread_sd=float(np.std(resid.to_numpy(dtype=float), ddof=1)),
    )

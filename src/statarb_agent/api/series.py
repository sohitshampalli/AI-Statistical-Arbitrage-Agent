"""Chart series derived from a stored daily ledger.

The dashboard draws an equity curve with a drawdown panel for each span of a
run (full, formation, validation). The paths are built here, in tested Python,
with the same definitions backtest.summary uses for the stored metrics:

- Returns are daily profit over a fixed capital (no reinvestment), so equity
  as a fraction of capital is 1 + cumulative sum of `ret`.
- The span starts from the capital (equity 1.0 before its first row), so a
  loss on the first day of the span counts as a drawdown.
- Drawdown on a row is (running peak - equity) / running peak, a positive
  fraction, with the starting 1.0 included in the running peak.

So the largest drawdown of the series equals the stored `max_drawdown` of the
span, which a test checks on a real run of the engine.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SpanSeries:
    """Equity and drawdown of one span.

    Attributes:
        dates: Dates of the ledger rows in the span.
        equity: Equity after each row, as a fraction of the fixed capital
            (1.0 is the capital at the start of the span).
        gross_equity: The same before trading costs and borrow fees.
        drawdown: Fall from the running peak on each row, a positive
            fraction of the peak; NaN on and after a row where equity is
            zero or below (the capital was lost).
    """

    dates: pd.DatetimeIndex
    equity: np.ndarray
    gross_equity: np.ndarray
    drawdown: np.ndarray


def span_series(daily: pd.DataFrame, start: str, end: str) -> SpanSeries:
    """Equity and drawdown paths of the rows dated in [start, end].

    Args:
        daily: A stored daily ledger with columns `ret` and `gross_ret`,
            indexed by date.
        start: First date of the span (ISO), as stored in the run's metrics.
        end: Last date of the span (ISO), inclusive.

    Raises:
        ValueError: If a column is missing or the span has no rows.
    """
    for column in ("ret", "gross_ret"):
        if column not in daily.columns:
            raise ValueError(f"daily ledger has no column {column!r}")
    index = pd.DatetimeIndex(daily.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    mask = (index >= pd.Timestamp(start)) & (index <= pd.Timestamp(end))
    rows = daily.loc[mask]
    if len(rows) == 0:
        raise ValueError(f"no ledger rows between {start} and {end}")
    ret = rows["ret"].to_numpy(dtype=float)
    gross = rows["gross_ret"].to_numpy(dtype=float)
    equity = 1.0 + np.cumsum(ret)
    gross_equity = 1.0 + np.cumsum(gross)
    path = np.concatenate([[1.0], equity])
    peak = np.maximum.accumulate(path)
    with np.errstate(divide="ignore", invalid="ignore"):
        drawdown = ((peak - path) / peak)[1:]
    lost = np.cumsum(path[1:] <= 0.0) > 0
    drawdown = np.where(lost, np.nan, drawdown)
    return SpanSeries(
        dates=index[mask], equity=equity, gross_equity=gross_equity, drawdown=drawdown
    )

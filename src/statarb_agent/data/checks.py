"""Data checks run before any pair analysis.

Two kinds of check, all on rows in [start, asof) only:

Fatal checks refuse the analysis:
- enough_history: at least min_obs rows.
- listed_throughout: trades from the first to the last reference trading day
  of the window.
- no_missing_days: no reference trading day is missing.
- no_extra_days: no bar on a day the reference did not trade.

Anomaly flags never refuse and never change data (yfinance repair is off).
They are recorded in the trial log and shown by the CLI:
- large_move: absolute daily log return of close above max_abs_log_return.
- large_distribution: a dividend plus capital gain above max_distribution_fraction
  of the previous close.
- stale_closes: a run of stale_run or more identical consecutive closes.

The reference calendar is the trading days of a reference ticker (SPY in this
project), taken from its own snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from statarb_agent.stats._asof import rows_before

MAX_ABS_LOG_RETURN = 0.4
MAX_DISTRIBUTION_FRACTION = 0.10
STALE_RUN = 5
SHOW = 5


@dataclass(frozen=True)
class DataCheck:
    """Result of one check.

    Attributes:
        name: Check name.
        passed: True if nothing was found.
        fatal: True if a failure refuses the analysis; False for a flag.
        detail: Human-readable finding, with dates.
    """

    name: str
    passed: bool
    fatal: bool
    detail: str


def _window(
    obj: pd.DataFrame | pd.DatetimeIndex, start: pd.Timestamp, asof: pd.Timestamp
) -> pd.DataFrame | pd.DatetimeIndex:
    if isinstance(obj, pd.DatetimeIndex):
        return obj[(obj >= start) & (obj < asof)]
    return rows_before(obj.loc[obj.index >= start], asof)


def _dates(index: pd.Index) -> str:
    shown = ", ".join(str(d.date()) for d in index[:SHOW])
    more = f", and {len(index) - SHOW} more" if len(index) > SHOW else ""
    return f"{shown}{more}"


def _stale_runs(close: pd.Series, min_run: int) -> list[tuple[pd.Timestamp, int]]:
    values = close.to_numpy()
    runs: list[tuple[pd.Timestamp, int]] = []
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[j + 1] == values[i]:
            j += 1
        if j - i + 1 >= min_run:
            runs.append((close.index[i], j - i + 1))
        i = j + 1
    return runs


def check_history(
    prices: pd.DataFrame,
    *,
    ticker: str,
    start: pd.Timestamp | str,
    asof: pd.Timestamp | str,
    calendar: pd.DatetimeIndex,
    min_obs: int,
    max_abs_log_return: float = MAX_ABS_LOG_RETURN,
    max_distribution_fraction: float = MAX_DISTRIBUTION_FRACTION,
    stale_run: int = STALE_RUN,
) -> list[DataCheck]:
    """Run every check on one ticker's rows in [start, asof).

    Args:
        prices: Output of a price source's load: needs close, dividends and
            capital_gains on a DatetimeIndex.
        ticker: Name used in messages.
        start, asof: The window. Rows on or after asof are never read.
        calendar: Reference trading days (only those in the window are used).
        min_obs: Minimum rows for enough_history.
        max_abs_log_return, max_distribution_fraction, stale_run: Flag
            thresholds.

    Returns:
        DataCheck objects in a fixed order: the four fatal checks, then the
        three flags.

    Raises:
        ValueError: If the reference calendar has no day in the window, or
            for any reason rows_before raises on `prices`.
    """
    first = pd.Timestamp(start)
    cutoff = pd.Timestamp(asof)
    days = _window(pd.DatetimeIndex(calendar), first, cutoff)
    if len(days) == 0:
        raise ValueError(f"reference calendar has no trading day in [{first.date()}, "
                         f"{cutoff.date()})")
    frame = _window(prices, first, cutoff)
    window = f"[{first.date()}, {cutoff.date()})"
    checks: list[DataCheck] = []

    n = len(frame)
    checks.append(DataCheck(
        "enough_history", n >= min_obs, True,
        f"{ticker} has {n} rows in {window}; at least {min_obs} required",
    ))

    starts_late = frame.index[0] > days[0]
    ends_early = frame.index[-1] < days[-1]
    parts = []
    if starts_late:
        parts.append(f"starts on {frame.index[0].date()}, after the first trading day "
                     f"{days[0].date()}")
    if ends_early:
        parts.append(f"ends on {frame.index[-1].date()}, before the last trading day "
                     f"{days[-1].date()}")
    checks.append(DataCheck(
        "listed_throughout", not parts, True,
        f"{ticker} " + " and ".join(parts) if parts
        else f"{ticker} trades from {days[0].date()} to {days[-1].date()}",
    ))

    missing = days.difference(frame.index)
    checks.append(DataCheck(
        "no_missing_days", len(missing) == 0, True,
        f"{ticker} is missing {len(missing)} trading days that the reference has: "
        f"{_dates(missing)}" if len(missing) else f"{ticker} has every trading day",
    ))
    extra = frame.index.difference(days)
    checks.append(DataCheck(
        "no_extra_days", len(extra) == 0, True,
        f"{ticker} has {len(extra)} bars on days the reference did not trade: "
        f"{_dates(extra)}" if len(extra) else f"{ticker} has no extra days",
    ))

    log_ret = np.log(frame["close"]).diff()
    big = log_ret.index[(log_ret.abs() > max_abs_log_return).to_numpy()]
    checks.append(DataCheck(
        "large_move", len(big) == 0, False,
        f"{ticker} has {len(big)} daily moves with absolute log return above "
        f"{max_abs_log_return}: {_dates(big)}" if len(big)
        else f"no absolute daily log return above {max_abs_log_return}",
    ))

    paid = frame["dividends"] + frame["capital_gains"]
    fraction = paid / frame["close"].shift(1)
    large = fraction.index[(fraction > max_distribution_fraction).to_numpy()]
    checks.append(DataCheck(
        "large_distribution", len(large) == 0, False,
        f"{ticker} has {len(large)} payments above {max_distribution_fraction:.0%} of "
        f"the previous close: {_dates(large)}" if len(large)
        else f"no payment above {max_distribution_fraction:.0%} of the previous close",
    ))

    runs = _stale_runs(frame["close"], stale_run)
    listing = ", ".join(f"{d.date()} ({k} days)" for d, k in runs[:SHOW])
    checks.append(DataCheck(
        "stale_closes", not runs, False,
        f"{ticker} has {len(runs)} runs of {stale_run} or more identical closes: "
        f"{listing}" if runs else f"no run of {stale_run} identical closes",
    ))
    return checks


def fatal_failures(checks: list[DataCheck]) -> list[DataCheck]:
    """The checks that refuse the analysis."""
    return [c for c in checks if c.fatal and not c.passed]


def flags(checks: list[DataCheck]) -> list[DataCheck]:
    """The anomaly flags that fired (never refuse)."""
    return [c for c in checks if not c.fatal and not c.passed]

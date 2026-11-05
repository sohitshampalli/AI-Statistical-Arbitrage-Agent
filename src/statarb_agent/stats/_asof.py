"""Shared look-ahead guard: select only rows strictly before an as-of date.

Every estimator in statarb_agent.stats calls rows_before first and never touches
the original object afterwards. All validation runs on the selected rows only, so
nothing at or after `asof` (values, NaNs, ordering) can change the result.
"""

from __future__ import annotations

import pandas as pd


def rows_before[T: (pd.Series, pd.DataFrame)](
    obj: T, asof: pd.Timestamp | str, *, min_obs: int = 1
) -> T:
    """Return the rows of `obj` whose index is strictly before `asof`.

    Args:
        obj: Series or DataFrame with a DatetimeIndex.
        asof: As-of date. Rows dated exactly `asof` are excluded.
        min_obs: Minimum number of rows required before `asof`.

    Returns:
        A new object of the same type holding only rows dated before `asof`.

    Raises:
        TypeError: If `obj` is not a Series or DataFrame or its index is not a
            DatetimeIndex, or if `asof` and the index disagree on time zone.
        ValueError: If the selected rows are fewer than `min_obs`, are not
            strictly increasing in date, or contain NaN.
    """
    if not isinstance(obj, (pd.Series, pd.DataFrame)):
        raise TypeError(
            f"expected a pandas Series or DataFrame, got {type(obj).__name__}"
        )
    if not isinstance(obj.index, pd.DatetimeIndex):
        raise TypeError(
            f"index must be a DatetimeIndex, got {type(obj.index).__name__}"
        )
    if min_obs < 1:
        raise ValueError(f"min_obs must be >= 1, got {min_obs!r}")

    cutoff = pd.Timestamp(asof)
    if cutoff is pd.NaT:
        raise ValueError("asof must be a valid date, got NaT")
    past = obj.loc[obj.index < cutoff]

    if len(past) < min_obs:
        raise ValueError(
            f"need at least {min_obs} rows before {cutoff.date()}, got {len(past)}"
        )
    if not (past.index.is_monotonic_increasing and past.index.is_unique):
        raise ValueError(
            "index before asof must be strictly increasing (sorted, no duplicates)"
        )
    if past.isna().to_numpy().any():
        raise ValueError("data before asof contains NaN")
    return past

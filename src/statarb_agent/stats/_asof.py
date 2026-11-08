"""Shared look-ahead guard: select only rows strictly before an as-of date.

Every estimator in statarb_agent.stats calls rows_before first and never touches
the original object afterwards. All validation runs on the selected rows only, so
nothing at or after `asof` (values, NaNs, ordering) can change the result.
"""

from __future__ import annotations

import numpy as np
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
        A new object of the same type holding only rows dated before `asof`,
        with index `freq` set to None (freq can depend on future rows).

    Raises:
        TypeError: If `obj` is not a Series or DataFrame or its index is not a
            DatetimeIndex, or if `asof` and the index disagree on time zone.
        ValueError: If the selected rows are fewer than `min_obs`, are not
            strictly increasing in date, or contain NaN or infinity. Only
            numeric columns are checked for infinity.
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
    if _contains_infinity(past):
        raise ValueError("data before asof contains infinity")
    # A DatetimeIndex `freq` is inferred from the whole index, so it can depend
    # on rows at or after asof. Drop it so no part of the output does.
    return past.set_axis(pd.DatetimeIndex(past.index, freq=None))


def _contains_infinity(obj: pd.Series | pd.DataFrame) -> bool:
    """True if any numeric value in `obj` is +inf or -inf. NaN is checked earlier."""
    frame = obj.to_frame() if isinstance(obj, pd.Series) else obj
    numeric = frame.select_dtypes(include="number")
    return bool(np.isinf(numeric.to_numpy(dtype=float)).any())


def paired_rows_before(
    a: pd.Series, b: pd.Series, asof: pd.Timestamp | str, *, min_obs: int = 1
) -> tuple[pd.Series, pd.Series]:
    """Apply rows_before to two legs and require identical dates afterwards.

    The legs are never joined: if their dates before `asof` differ in any way
    (a missing day, an extra day, a shifted day), this raises instead of
    silently dropping rows. Dates at or after `asof` are not compared.

    Raises:
        ValueError: If the two legs have different dates before `asof`, or for
            any reason rows_before raises ValueError.
    """
    past_a = rows_before(a, asof, min_obs=min_obs)
    past_b = rows_before(b, asof, min_obs=min_obs)
    if not past_a.index.equals(past_b.index):
        raise ValueError(
            "the two legs have different dates before asof "
            f"({len(past_a)} vs {len(past_b)} rows); align them explicitly first"
        )
    return past_a, past_b

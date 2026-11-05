"""Tests for the shared look-ahead guard rows_before."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from statarb_agent.stats._asof import rows_before


def _series(n: int = 10) -> pd.Series:
    idx = pd.bdate_range("2000-01-03", periods=n, name="date")
    return pd.Series(np.arange(n, dtype=float), index=idx)


def test_excludes_asof_row_and_keeps_earlier_rows() -> None:
    s = _series()
    asof = s.index[4]
    past = rows_before(s, asof)
    assert len(past) == 4
    assert past.index.max() < asof
    assert asof not in past.index
    pd.testing.assert_series_equal(past, s.iloc[:4])


def test_asof_between_dates() -> None:
    s = _series()  # 2000-01-03 is a Monday, so 2000-01-08 is a Saturday
    past = rows_before(s, "2000-01-08")
    pd.testing.assert_series_equal(past, s.iloc[:5])


def test_accepts_string_and_timestamp() -> None:
    s = _series()
    pd.testing.assert_series_equal(
        rows_before(s, "2000-01-06"), rows_before(s, pd.Timestamp("2000-01-06"))
    )


def test_dataframe() -> None:
    s = _series()
    df = pd.DataFrame({"a": s, "b": -s})
    past = rows_before(df, s.index[3])
    pd.testing.assert_frame_equal(past, df.iloc[:3])


def test_future_rows_do_not_change_result() -> None:
    s = _series(20)
    asof = s.index[10]
    before = rows_before(s, asof)
    perturbed = s.copy()
    perturbed.iloc[10:] = np.random.default_rng(0).standard_normal(10) * 1e6
    perturbed.iloc[12] = np.nan  # NaN in the future must not raise
    pd.testing.assert_series_equal(
        rows_before(perturbed, asof), before, check_exact=True
    )


def test_result_is_independent_of_original() -> None:
    s = _series()
    past = rows_before(s, s.index[5])
    past.iloc[0] = 99.0
    assert s.iloc[0] == 0.0


def test_too_few_rows() -> None:
    s = _series()
    with pytest.raises(ValueError):
        rows_before(s, s.index[0])  # nothing strictly before the first row
    with pytest.raises(ValueError):
        rows_before(s, s.index[3], min_obs=4)
    assert len(rows_before(s, s.index[3], min_obs=3)) == 3


def test_nan_before_asof_raises() -> None:
    s = _series()
    s.iloc[2] = np.nan
    with pytest.raises(ValueError):
        rows_before(s, s.index[5])


def test_unsorted_or_duplicate_index_raises() -> None:
    s = _series()
    with pytest.raises(ValueError):
        rows_before(s.iloc[[1, 0, 2, 3]], s.index[5])
    with pytest.raises(ValueError):
        rows_before(s.iloc[[0, 1, 1, 2]], s.index[5])


def test_bad_types_raise() -> None:
    with pytest.raises(TypeError):
        rows_before(np.arange(5.0), "2000-01-05")  # type: ignore[type-var]
    with pytest.raises(TypeError):
        rows_before(pd.Series([1.0, 2.0]), "2000-01-05")
    with pytest.raises(ValueError):
        rows_before(_series(), "2000-01-05", min_obs=0)

"""Tests for the shared look-ahead guard rows_before."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from statarb_agent.stats._asof import paired_rows_before, rows_before


def _series(n: int = 10) -> pd.Series:
    idx = pd.bdate_range("2000-01-03", periods=n, name="date")
    return pd.Series(np.arange(n, dtype=float), index=idx)


def _nofreq[T: (pd.Series, pd.DataFrame)](obj: T) -> T:
    """Expected rows_before output: same rows, index freq cleared."""
    return obj.set_axis(pd.DatetimeIndex(obj.index, freq=None))


def test_excludes_asof_row_and_keeps_earlier_rows() -> None:
    s = _series()
    asof = s.index[4]
    past = rows_before(s, asof)
    assert len(past) == 4
    assert past.index.max() < asof
    assert asof not in past.index
    pd.testing.assert_series_equal(past, _nofreq(s.iloc[:4]))


def test_asof_between_dates() -> None:
    s = _series()  # 2000-01-03 is a Monday, so 2000-01-08 is a Saturday
    past = rows_before(s, "2000-01-08")
    pd.testing.assert_series_equal(past, _nofreq(s.iloc[:5]))


def test_accepts_string_and_timestamp() -> None:
    s = _series()
    pd.testing.assert_series_equal(
        rows_before(s, "2000-01-06"), rows_before(s, pd.Timestamp("2000-01-06"))
    )


def test_dataframe() -> None:
    s = _series()
    df = pd.DataFrame({"a": s, "b": -s})
    past = rows_before(df, s.index[3])
    pd.testing.assert_frame_equal(past, _nofreq(df.iloc[:3]))


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


def test_freq_cleared_so_future_rows_cannot_change_index_metadata() -> None:
    s = _series(20)
    asof = s.index[10]
    full = rows_before(s, asof)
    gap = rows_before(s.drop(s.index[15]), asof)  # removing a future row drops freq
    assert full.index.freq is None and gap.index.freq is None
    pd.testing.assert_series_equal(full, gap, check_exact=True)
    assert s.index.freq is not None  # the caller's object is not modified


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


@pytest.mark.parametrize("value", [np.inf, -np.inf])
@pytest.mark.parametrize("row", [0, 2, 4])  # 4 is the last row before asof
def test_infinity_before_asof_raises(row: int, value: float) -> None:
    s = _series()
    s.iloc[row] = value
    with pytest.raises(ValueError, match="infinity"):
        rows_before(s, s.index[5])
    df = pd.DataFrame({"a": _series(), "b": s})
    with pytest.raises(ValueError, match="infinity"):
        rows_before(df, s.index[5])


@pytest.mark.parametrize("value", [np.inf, -np.inf])
@pytest.mark.parametrize("row", [5, 8])  # 5 is the asof row itself
def test_infinity_at_or_after_asof_does_not_change_result(
    row: int, value: float
) -> None:
    s = _series()
    asof = s.index[5]
    before = rows_before(s, asof)
    s.iloc[row] = value
    pd.testing.assert_series_equal(rows_before(s, asof), before, check_exact=True)


def test_infinity_check_skips_non_numeric_columns() -> None:
    s = _series()
    df = pd.DataFrame({"a": s, "label": ["x"] * len(s)})
    pd.testing.assert_frame_equal(rows_before(df, s.index[5]), _nofreq(df.iloc[:5]))
    df.loc[df.index[1], "a"] = np.inf
    with pytest.raises(ValueError, match="infinity"):
        rows_before(df, s.index[5])


def test_paired_infinity_in_either_leg_raises() -> None:
    a, b = _pair()
    a_inf = a.copy()
    a_inf.iloc[3] = np.inf
    b_inf = b.copy()
    b_inf.iloc[3] = -np.inf
    with pytest.raises(ValueError, match="infinity"):
        paired_rows_before(a_inf, b, a.index[6])
    with pytest.raises(ValueError, match="infinity"):
        paired_rows_before(a, b_inf, a.index[6])


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


def _pair(n: int = 10) -> tuple[pd.Series, pd.Series]:
    s = _series(n)
    return s.rename("a"), (2.0 * s).rename("b")


def test_paired_returns_both_legs_before_asof() -> None:
    a, b = _pair()
    pa, pb = paired_rows_before(a, b, a.index[6])
    pd.testing.assert_series_equal(pa, _nofreq(a.iloc[:6]))
    pd.testing.assert_series_equal(pb, _nofreq(b.iloc[:6]))


def test_paired_mismatched_dates_before_asof_raise() -> None:
    a, b = _pair()
    with pytest.raises(ValueError):
        paired_rows_before(a, b.drop(b.index[2]), a.index[6])  # b misses a day
    shifted = b.copy()
    shifted.index = shifted.index + pd.offsets.BDay(1)
    with pytest.raises(ValueError):
        paired_rows_before(a, shifted, a.index[6])  # same length, shifted dates


def test_paired_mismatch_only_after_asof_is_ignored() -> None:
    a, b = _pair()
    asof = a.index[6]
    expected = paired_rows_before(a, b, asof)
    pa, pb = paired_rows_before(a, b.drop(b.index[8]), asof)
    pd.testing.assert_series_equal(pa, expected[0])
    pd.testing.assert_series_equal(pb, expected[1])

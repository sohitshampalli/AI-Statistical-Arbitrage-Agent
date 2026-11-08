"""Tests for align_pair: identical calendars pass, mismatches refuse with dates."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from statarb_agent.data.alignment import AlignmentError, align_pair


def _series(n: int = 40, start: str = "2015-01-02", name: str = "x") -> pd.Series:
    idx = pd.bdate_range(start, periods=n, name="date")
    return pd.Series(np.linspace(1.0, 2.0, n), index=idx, name=name)


def test_identical_calendars_pass_unchanged() -> None:
    a, b = _series(name="a"), _series(name="b") * 3.0
    asof = a.index[30]
    a2, b2, report = align_pair(a, b, asof=asof, label_a="KO", label_b="PEP")
    pd.testing.assert_index_equal(a2.index, b2.index)
    assert len(a2) == 30 and a2.index.max() < asof
    assert report.n_a == report.n_b == report.n_common == 30
    assert report.only_in_a == report.only_in_b == () and not report.dropped
    assert report.label_a == "KO" and report.asof == str(asof.date())


def test_start_bounds_the_window() -> None:
    a, b = _series(), _series()
    a2, _, report = align_pair(a, b, asof=a.index[30], start=a.index[10])
    assert a2.index[0] == a.index[10] and len(a2) == 20
    assert report.start == str(a.index[10].date())


def test_missing_day_is_refused_and_listed() -> None:
    a, b = _series(), _series()
    gap = b.index[12]
    with pytest.raises(AlignmentError) as info:
        align_pair(a, b.drop(gap), asof=a.index[30], label_a="KO", label_b="PEP")
    report = info.value.report
    assert report.only_in_a == (str(gap.date()),) and report.only_in_b == ()
    message = str(info.value)
    assert str(gap.date()) in message and "KO only: 1" in message
    assert "not joined or filled silently" in message


def test_shifted_dates_are_refused() -> None:
    a = _series()
    b = _series()
    b.index = b.index + pd.offsets.BDay(1)
    with pytest.raises(AlignmentError) as info:
        align_pair(a, b, asof=a.index[30])
    # a's first day is unmatched; b's extra last day falls after asof and is ignored
    assert info.value.report.only_in_a == (str(a.index[0].date()),)
    assert info.value.report.only_in_b == ()


def test_long_listing_is_shortened() -> None:
    a, b = _series(), _series()
    with pytest.raises(AlignmentError, match="and 3 more"):
        align_pair(a, b.drop(b.index[2:10]), asof=a.index[30])


def test_allowed_mismatch_is_dropped_and_reported() -> None:
    a, b = _series(), _series()
    extra_a, extra_b = a.index[5], b.index[7]
    a2, b2, report = align_pair(
        a.drop(extra_b), b.drop(extra_a), asof=a.index[30], max_unmatched_days=2
    )
    pd.testing.assert_index_equal(a2.index, b2.index)
    assert extra_a not in a2.index and extra_b not in a2.index
    assert report.dropped and report.n_unmatched == 2
    assert report.only_in_a == (str(extra_a.date()),)
    assert report.only_in_b == (str(extra_b.date()),)
    with pytest.raises(AlignmentError):
        align_pair(a.drop(extra_b), b.drop(extra_a), asof=a.index[30],
                   max_unmatched_days=1)


def test_mismatch_and_changes_at_or_after_asof_are_ignored() -> None:
    """Look-ahead test: dates and values on or after asof never matter."""
    a, b = _series(), _series()
    asof = a.index[30]
    before = align_pair(a, b, asof=asof)
    a_changed = a.copy()
    a_changed.iloc[30:] = np.nan  # includes the asof row
    b_changed = b.drop(b.index[[30, 33]])
    after = align_pair(a_changed, b_changed, asof=asof)
    pd.testing.assert_series_equal(after[0], before[0], check_exact=True)
    pd.testing.assert_series_equal(after[1], before[1], check_exact=True)
    assert after[2] == before[2]


def test_negative_allowance_raises() -> None:
    with pytest.raises(ValueError):
        align_pair(_series(), _series(), asof="2016-01-01", max_unmatched_days=-1)

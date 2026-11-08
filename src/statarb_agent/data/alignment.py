"""Explicit calendar alignment of two price series.

Two tickers can disagree on trading days (a missing bar, an extra bar). Nothing
here joins silently: align_pair compares the dates in [start, asof) and, by
default, refuses any mismatch and lists the dates. Dropping unmatched dates
is allowed only up to max_unmatched_days, and the report lists every dropped
date so the trial log can record it. After alignment both series have
identical indexes, as paired_rows_before requires.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from statarb_agent.stats._asof import rows_before

SHOW_DATES = 5


@dataclass(frozen=True)
class AlignmentReport:
    """What align_pair found and did.

    Attributes:
        label_a, label_b: Names of the two series (tickers).
        start: First date considered (ISO), or None for no lower bound.
        asof: As-of date (ISO); only dates strictly before it are considered.
        n_a, n_b: Rows of each series in the window.
        n_common: Dates present in both.
        only_in_a, only_in_b: ISO dates present in one series only.
        dropped: True if unmatched dates were removed.
    """

    label_a: str
    label_b: str
    start: str | None
    asof: str
    n_a: int
    n_b: int
    n_common: int
    only_in_a: tuple[str, ...] = field(default_factory=tuple)
    only_in_b: tuple[str, ...] = field(default_factory=tuple)
    dropped: bool = False

    @property
    def n_unmatched(self) -> int:
        return len(self.only_in_a) + len(self.only_in_b)


class AlignmentError(ValueError):
    """The two series disagree on more dates than allowed."""

    def __init__(self, message: str, report: AlignmentReport) -> None:
        super().__init__(message)
        self.report = report


def _window(series: pd.Series, start: pd.Timestamp | None, asof: pd.Timestamp) -> pd.Series:
    if start is not None:
        series = series.loc[series.index >= start]
    return rows_before(series, asof)


def _listing(label: str, dates: tuple[str, ...]) -> str:
    shown = ", ".join(dates[:SHOW_DATES])
    more = f", and {len(dates) - SHOW_DATES} more" if len(dates) > SHOW_DATES else ""
    return f"{label} only: {len(dates)} ({shown}{more})"


def align_pair(
    a: pd.Series,
    b: pd.Series,
    *,
    asof: pd.Timestamp | str,
    start: pd.Timestamp | str | None = None,
    max_unmatched_days: int = 0,
    label_a: str = "A",
    label_b: str = "B",
) -> tuple[pd.Series, pd.Series, AlignmentReport]:
    """Return both series on identical dates in [start, asof), or refuse.

    Args:
        a, b: Series with a DatetimeIndex.
        asof: Only dates strictly before it are compared or returned.
        start: Optional first date.
        max_unmatched_days: How many dates present in only one series may be
            dropped. The default 0 refuses any mismatch.
        label_a, label_b: Names used in the report and messages.

    Returns:
        (a_aligned, b_aligned, report).

    Raises:
        AlignmentError: If more than max_unmatched_days dates are unmatched.
            The message lists the first dates on each side.
        ValueError: For any reason rows_before raises on either series.
    """
    if max_unmatched_days < 0:
        raise ValueError("max_unmatched_days must be >= 0")
    cutoff = pd.Timestamp(asof)
    first = None if start is None else pd.Timestamp(start)
    wa = _window(a, first, cutoff)
    wb = _window(b, first, cutoff)
    only_a = tuple(str(d.date()) for d in wa.index.difference(wb.index))
    only_b = tuple(str(d.date()) for d in wb.index.difference(wa.index))
    common = wa.index.intersection(wb.index)
    report = AlignmentReport(
        label_a=label_a,
        label_b=label_b,
        start=None if first is None else str(first.date()),
        asof=str(cutoff.date()),
        n_a=len(wa),
        n_b=len(wb),
        n_common=len(common),
        only_in_a=only_a,
        only_in_b=only_b,
        dropped=bool(only_a or only_b),
    )
    if report.n_unmatched > max_unmatched_days:
        raise AlignmentError(
            f"Cannot align {label_a}/{label_b} before {report.asof}: "
            f"{report.n_unmatched} dates are in one series only, "
            f"{max_unmatched_days} allowed. {_listing(label_a, only_a)}; "
            f"{_listing(label_b, only_b)}. Dates are not joined or filled silently.",
            report,
        )
    return wa.loc[common], wb.loc[common], report

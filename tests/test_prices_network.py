"""One live download, to check what the offline tests can only assume.

Approved scope (2026-11-08): one ticker (KO), one download, 2010-01-01 to the
lock date, run once. The split date is read from the downloaded Splits column,
never hard-coded. Assertions only where the data clearly supports them:

- no move above 10 percent in tr_close on a split date (Close is split-adjusted);
- each payment below 5 percent of the previous close, on both sides of the
  split (dividends are on the same split basis as Close).

The gap between tr_close and Yahoo's Adj Close is reported, not asserted.

The data goes to a temporary folder and is never kept or committed. The check
logic in `_check_snapshot` is first run offline on a synthetic snapshot
(test_checks_on_a_synthetic_snapshot), so the live run exercises proven code.
"""

from __future__ import annotations

import importlib.metadata
import warnings
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from statarb_agent.sources.base import ManifestEntry, SnapshotStore
from statarb_agent.sources.prices import (
    PriceRequest,
    YFinancePrices,
    distribution_yields,
    normalise_yfinance,
    split_day_returns,
    total_return_gap,
)
from statarb_agent.study import TEST_START, load_study

REPO_ROOT = Path(__file__).resolve().parents[1]
STUDY = load_study(REPO_ROOT / "configs" / "study.yaml")
TICKER = "KO"
START = "2010-01-01"
SPLIT_MOVE_MAX = 0.10
YIELD_MAX = 0.05


def _check_snapshot(
    src: YFinancePrices, entry: ManifestEntry, report: Callable[[str], None]
) -> None:
    raw = src.store.read(entry)
    frame = normalise_yfinance(raw, entry.key)
    report(
        f"{entry.key}: {len(frame)} rows, {frame.index[0].date()} to "
        f"{frame.index[-1].date()}, source tz {raw.index.tz}, columns "
        f"{list(raw.columns)}"
    )
    report(f"snapshot {entry.snapshot_id}, file sha256 {entry.file_sha256[:16]}..., "
           f"notes {list(entry.notes)}")

    moves = split_day_returns(frame)
    yields = distribution_yields(frame)
    if moves.empty:
        report("splits: none in the Splits column; split checks not asserted")
    for day, row in moves.iterrows():
        report(
            f"split on {day.date()} (read from data): ratio {row['ratio']:g}, "
            f"close return {row['close_return']:+.4%}, tr_close return "
            f"{row['tr_return']:+.4%}"
        )
    report(f"payments: {len(yields)}, max yield on previous close {yields.max():.4%}"
           if len(yields) else "payments: none")

    gap = total_return_gap(frame)
    report(
        f"tr_close vs Adj Close: max abs daily log-return difference "
        f"{gap.max_abs_daily_log_diff:.3e} on {gap.worst_date.date()}, range of "
        f"log(tr_close / adj_close) {gap.log_ratio_range:.3e} (reported, not asserted)"
    )

    for day, row in moves.iterrows():
        assert abs(row["tr_return"]) < SPLIT_MOVE_MAX, f"tr_close jumps on {day.date()}"
    if not moves.empty:
        first_split = moves.index[0]
        before = yields[yields.index < first_split]
        after = yields[yields.index >= first_split]
        report(
            f"payments before first split: {len(before)}, max "
            f"{before.max() if len(before) else float('nan'):.4%}; after: "
            f"{len(after)}, max {after.max() if len(after) else float('nan'):.4%}"
        )
        if len(before) and len(after):
            assert (before < YIELD_MAX).all() and (after < YIELD_MAX).all()
        else:
            report("payments missing on one side of the split; yields not asserted")


def test_checks_on_a_synthetic_snapshot(
    tmp_path: Path, report_line: Callable[[str], None]
) -> None:
    """Offline run of the same checks on a frame with a split and dividends."""
    n = 300
    idx = pd.bdate_range("2012-01-03", periods=n, tz="America/New_York", name="Date")
    close = 40.0 * np.exp(np.cumsum(0.01 * np.random.default_rng(1).standard_normal(n)))
    div = np.zeros(n)
    div[30::63] = 0.3
    splits = np.zeros(n)
    splits[150] = 2.0
    raw = pd.DataFrame(
        {
            "Open": close, "High": close, "Low": close, "Close": close,
            "Adj Close": close, "Volume": np.full(n, 1, dtype="int64"),
            "Dividends": div, "Stock Splits": splits,
        },
        index=idx,
    )
    store = SnapshotStore(tmp_path / "data", repo_root=REPO_ROOT)
    src = YFinancePrices(
        store, study=STUDY, downloader=lambda t, s, e: raw.copy(), pause_s=0.0
    )
    entry = src.fetch(PriceRequest(TICKER, START, str(TEST_START.date())))
    lines: list[str] = []
    _check_snapshot(src, entry, lines.append)
    assert any(f"split on {idx[150].date()}" in line for line in lines)
    assert any("payments before first split: 2" in line for line in lines)


@pytest.mark.network
def test_live_ko_download(tmp_path: Path, report_line: Callable[[str], None]) -> None:
    store = SnapshotStore(tmp_path / "data", repo_root=REPO_ROOT)
    src = YFinancePrices(store, study=STUDY, pause_s=0.0)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        entry = src.fetch(PriceRequest(TICKER, START, str(TEST_START.date())))
    report_line(f"yfinance {importlib.metadata.version('yfinance')}, request {dict(entry.request)}")
    report_line(
        f"warnings during download: {len(caught)}"
        + "".join(f"; {w.category.__name__}: {str(w.message)[:120]}" for w in caught[:5])
    )
    _check_snapshot(src, entry, report_line)

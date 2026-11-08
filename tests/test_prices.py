"""Tests for the yfinance price source, on synthetic yfinance-shaped frames.

No test here touches the network: a fake downloader returns frames built in
code with yfinance's columns, dtypes and timezone. A real download is never
committed as a fixture, because downloaded data stays out of git.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from statarb_agent.sources.base import (
    NotCachedError,
    SnapshotMissingError,
    SnapshotStore,
)
from statarb_agent.sources.prices import (
    HISTORY_KWARGS,
    LOAD_COLUMNS,
    DownloadError,
    PriceRequest,
    YFinancePrices,
    check_price_values,
    distribution_yields,
    normalise_yfinance,
    split_day_returns,
    total_return_gap,
    total_return_index,
    unadjusted_close,
)
from statarb_agent.study import TEST_START, LockedPeriodError, load_study

REPO_ROOT = Path(__file__).resolve().parents[1]
STUDY = load_study(REPO_ROOT / "configs" / "study.yaml")  # locked: no prereg file
T0 = pd.Timestamp("2026-11-08 10:00", tz="UTC")


def yahoo_adj_close(close: np.ndarray, dividends: np.ndarray) -> np.ndarray:
    """Adj Close built the way this test assumes Yahoo builds it.

    adj[t] = close[t] times the product, over ex-dates e after t, of
    (1 - D[e] / close[e-1]).
    """
    factor = np.ones_like(close)
    factor[1:] = 1.0 - dividends[1:] / close[:-1]
    after = np.ones_like(close)
    after[:-1] = np.cumprod(factor[::-1])[::-1][1:]
    return close * after


def yahoo_frame(
    close: list[float] | np.ndarray,
    *,
    dividends: list[float] | np.ndarray | None = None,
    splits: list[float] | np.ndarray | None = None,
    capital_gains: list[float] | np.ndarray | None = None,
    start: str = "2015-01-02",
) -> pd.DataFrame:
    """A frame shaped like Ticker.history(auto_adjust=False, actions=True)."""
    c = np.asarray(close, dtype=float)
    n = len(c)
    d = np.zeros(n) if dividends is None else np.asarray(dividends, dtype=float)
    s = np.zeros(n) if splits is None else np.asarray(splits, dtype=float)
    idx = pd.bdate_range(start, periods=n, tz="America/New_York", name="Date")
    frame = pd.DataFrame(
        {
            "Open": c * 0.995,
            "High": c * 1.01,
            "Low": c * 0.99,
            "Close": c,
            "Adj Close": yahoo_adj_close(c, d),
            "Volume": np.full(n, 1000, dtype="int64"),
            "Dividends": d,
            "Stock Splits": s,
        },
        index=idx,
    )
    if capital_gains is not None:
        frame["Capital Gains"] = np.asarray(capital_gains, dtype=float)
    return frame


def walk(n: int, seed: int = 0, start_price: float = 50.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return start_price * np.exp(np.cumsum(0.01 * rng.standard_normal(n)))


class FakeDownloader:
    """Returns prepared frames and records every call."""

    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self.frames = frames
        self.calls: list[tuple[str, str, str]] = []

    def __call__(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        self.calls.append((ticker, start, end))
        return self.frames[ticker].copy()


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> pd.Timestamp:
        self.now = self.now + pd.Timedelta(minutes=1)
        return self.now


def source(
    tmp_path: Path, frames: dict[str, pd.DataFrame], **kwargs: object
) -> tuple[YFinancePrices, FakeDownloader]:
    fake = FakeDownloader(frames)
    store = SnapshotStore(tmp_path / "data", repo_root=REPO_ROOT)
    src = YFinancePrices(
        store, study=STUDY, downloader=fake, clock=Clock(), pause_s=0.0, **kwargs
    )
    return src, fake


# Normalising -------------------------------------------------------------


def test_normalise_renames_and_strips_timezone() -> None:
    raw = yahoo_frame([10.0, 11.0, 12.0])
    out = normalise_yfinance(raw, "KO")
    assert list(out.columns) == [
        "open", "high", "low", "close", "adj_close", "volume",
        "dividends", "splits", "capital_gains",
    ]
    assert out.index.name == "date" and out.index.tz is None
    assert out.index[0] == pd.Timestamp("2015-01-02")
    assert (out["capital_gains"] == 0.0).all()
    assert out["volume"].dtype == "int64" and out["close"].dtype == "float64"
    np.testing.assert_array_equal(out["close"].to_numpy(), [10.0, 11.0, 12.0])


def test_normalise_keeps_capital_gains_for_funds() -> None:
    raw = yahoo_frame([10.0, 11.0], capital_gains=[0.0, 0.3])
    assert normalise_yfinance(raw, "EWA")["capital_gains"].tolist() == [0.0, 0.3]


@pytest.mark.parametrize(
    "change",
    ["drop_column", "extra_column", "naive_index", "intraday_stamp"],
)
def test_normalise_refuses_unexpected_structure(change: str) -> None:
    raw = yahoo_frame([10.0, 11.0, 12.0])
    if change == "drop_column":
        raw = raw.drop(columns="Adj Close")
    elif change == "extra_column":
        raw["Repaired?"] = False
    elif change == "naive_index":
        raw.index = raw.index.tz_localize(None)
    else:
        raw.index = raw.index + pd.Timedelta(hours=16)
    with pytest.raises(ValueError):
        normalise_yfinance(raw, "KO")


@pytest.mark.parametrize("change", ["zero_close", "nan_close", "negative_div", "dup_date"])
def test_value_checks(change: str) -> None:
    frame = normalise_yfinance(yahoo_frame([10.0, 11.0, 12.0]), "KO")
    if change == "zero_close":
        frame.iloc[1, frame.columns.get_loc("close")] = 0.0
    elif change == "nan_close":
        frame.iloc[1, frame.columns.get_loc("close")] = np.nan
    elif change == "negative_div":
        frame.iloc[1, frame.columns.get_loc("dividends")] = -0.1
    else:
        frame = frame.iloc[[0, 1, 1, 2]]
    with pytest.raises(ValueError):
        check_price_values(frame, "KO")


# Total-return index and split reconstruction --------------------------------


def test_total_return_index_known_values() -> None:
    idx = pd.bdate_range("2015-01-02", periods=4)
    close = pd.Series([10.0, 10.5, 10.2, 10.4], index=idx)
    div = pd.Series([0.0, 0.0, 0.5, 0.0], index=idx)
    tr = total_return_index(close, div)
    expected = [10.0, 10.5, 10.5 * 10.7 / 10.5, 10.7 * 10.4 / 10.2]
    np.testing.assert_allclose(tr.to_numpy(), expected, rtol=0, atol=1e-12)
    assert tr.name == "tr_close"


def test_capital_gains_count_like_dividends() -> None:
    idx = pd.bdate_range("2015-01-02", periods=3)
    close = pd.Series([10.0, 9.8, 10.0], index=idx)
    paid = pd.Series([0.0, 0.3, 0.0], index=idx)
    zero = pd.Series(0.0, index=idx)
    pd.testing.assert_series_equal(
        total_return_index(close, paid), total_return_index(close, zero, paid)
    )


def test_total_return_row_t_depends_only_on_rows_up_to_t() -> None:
    n, k = 60, 30
    idx = pd.bdate_range("2015-01-02", periods=n)
    close = pd.Series(walk(n), index=idx)
    div = pd.Series(0.0, index=idx)
    div.iloc[[10, 25, 40, 55]] = 0.4
    base = total_return_index(close, div)
    later = close.copy()
    later.iloc[k + 1 :] *= 3.0
    later_div = div.copy()
    later_div.iloc[k + 1 :] = 2.0  # new, large dividends after row k
    changed = total_return_index(later, later_div)
    np.testing.assert_array_equal(changed.to_numpy()[: k + 1], base.to_numpy()[: k + 1])


def test_split_adjusted_close_has_no_jump_and_raw_price_is_recovered() -> None:
    raw_close = np.array([100.0, 102.0, 51.0, 52.0, 26.5])  # 2:1 on day 2, 2:1 on day 4
    splits = np.array([0.0, 0.0, 2.0, 0.0, 2.0])
    yahoo_close = np.array([25.0, 25.5, 25.5, 26.0, 26.5])  # adjusted to the end
    frame = normalise_yfinance(yahoo_frame(yahoo_close, splits=splits), "X")
    raw = unadjusted_close(frame["close"], frame["splits"])
    np.testing.assert_allclose(raw.to_numpy(), raw_close, rtol=0, atol=1e-12)
    moves = split_day_returns(frame)
    assert list(moves.index) == [frame.index[2], frame.index[4]]
    assert moves["ratio"].tolist() == [2.0, 2.0]
    assert (moves["tr_return"].abs() < 0.10).all()
    np.testing.assert_allclose(moves["close_return"], moves["tr_return"], atol=1e-15)


def test_split_day_returns_and_yields_are_empty_without_events() -> None:
    frame = normalise_yfinance(yahoo_frame(walk(20)), "X")
    assert split_day_returns(frame).empty
    assert distribution_yields(frame).empty


def test_distribution_yields_expose_a_split_basis_mismatch() -> None:
    """If dividends were left unadjusted while Close is adjusted, the yield
    before a 2:1 split would double. The diagnostic must show that."""
    close = np.full(8, 25.0)
    splits = np.zeros(8)
    splits[5] = 2.0
    adjusted_div = np.zeros(8)
    adjusted_div[[2, 7]] = 0.25  # one percent of 25 on both sides
    unadjusted_div = adjusted_div.copy()
    unadjusted_div[2] = 0.50  # pre-split amount in pre-split dollars
    good = distribution_yields(
        normalise_yfinance(yahoo_frame(close, dividends=adjusted_div, splits=splits), "X")
    )
    bad = distribution_yields(
        normalise_yfinance(
            yahoo_frame(close, dividends=unadjusted_div, splits=splits), "X"
        )
    )
    np.testing.assert_allclose(good.to_numpy(), [0.01, 0.01], atol=1e-15)
    np.testing.assert_allclose(bad.to_numpy(), [0.02, 0.01], atol=1e-15)


def test_total_return_gap_against_yahoo_style_adj_close() -> None:
    close = np.array([20.0, 20.4, 20.1, 20.3, 20.6])
    div = np.array([0.0, 0.0, 0.3, 0.0, 0.0])
    frame = normalise_yfinance(yahoo_frame(close, dividends=div), "X")
    gap = total_return_gap(frame)
    expected = math.log((20.1 + 0.3) / 20.4) - math.log(20.1 / (20.4 - 0.3))
    assert gap.max_abs_daily_log_diff == pytest.approx(abs(expected), abs=1e-12)
    assert gap.worst_date == frame.index[2]
    assert gap.log_ratio_range == pytest.approx(abs(expected), abs=1e-12)
    flat = total_return_gap(normalise_yfinance(yahoo_frame(close), "X"))
    # tr_close is a running product of close ratios, so it matches close only to
    # rounding (4.4e-16 measured), not exactly.
    assert flat.max_abs_daily_log_diff < 1e-12 and flat.log_ratio_range < 1e-12


# Fetch ------------------------------------------------------------------------


def test_fetch_records_request_and_clips_to_the_lock(tmp_path: Path) -> None:
    frame = yahoo_frame(walk(30), start="2021-11-15")
    src, fake = source(tmp_path, {"BRK-B": frame})
    entry = src.fetch(PriceRequest("brk.b", "2010-01-01", "2026-11-08"))
    assert fake.calls == [("BRK-B", "2010-01-01", "2022-01-01")]
    assert entry.key == "BRK-B" and entry.source == "yfinance"
    assert entry.url == "https://query2.finance.yahoo.com/v8/finance/chart/BRK-B"
    assert entry.request == {
        "ticker": "BRK-B",
        "start": "2010-01-01",
        "end": "2022-01-01",
        "requested_end": "2026-11-08",
        **HISTORY_KWARGS,
    }
    assert entry.request["repair"] is False and entry.request["auto_adjust"] is False
    assert any("clipped" in note for note in entry.notes)
    stored = src.store.read(entry)
    assert list(stored.columns) == list(frame.columns)  # raw, as delivered
    assert str(stored.index.tz) == "America/New_York"
    assert stored.index.tz_localize(None).max() < TEST_START


def test_fetch_drops_rows_the_source_returns_after_the_lock(tmp_path: Path) -> None:
    frame = yahoo_frame(walk(30), start="2021-12-15")  # runs into January 2022
    src, _ = source(tmp_path, {"KO": frame})
    entry = src.fetch(PriceRequest("KO", "2021-12-01", "2022-01-01"))
    stored = src.store.read(entry)
    assert stored.index.tz_localize(None).max() == pd.Timestamp("2021-12-31")
    assert any("dropped" in note for note in entry.notes)
    assert entry.last_date is not None and entry.last_date < "2022-01-01"


def test_fetch_empty_response_mentions_survivorship(tmp_path: Path) -> None:
    src, _ = source(tmp_path, {"GONE": yahoo_frame(walk(5)).iloc[:0]})
    with pytest.raises(DownloadError, match="survivorship"):
        src.fetch(PriceRequest("GONE", "2010-01-01", "2020-01-01"))
    assert src.store.manifest.entries() == []


def test_fetch_refuses_malformed_response(tmp_path: Path) -> None:
    src, _ = source(tmp_path, {"KO": yahoo_frame(walk(5)).drop(columns="Dividends")})
    with pytest.raises(ValueError, match="unexpected yfinance columns"):
        src.fetch(PriceRequest("KO", "2010-01-01", "2020-01-01"))
    assert src.store.manifest.entries() == []


@pytest.mark.parametrize("bad", ["../KO", "KO/..", "ıBM", ""])
def test_fetch_validates_ticker_before_downloading(tmp_path: Path, bad: str) -> None:
    src, fake = source(tmp_path, {})
    with pytest.raises(ValueError):
        src.fetch(PriceRequest(bad, "2010-01-01", "2020-01-01"))
    assert fake.calls == []


def test_fetch_many_pauses_between_tickers(tmp_path: Path) -> None:
    pauses: list[float] = []
    frames = {t: yahoo_frame(walk(10, seed=i)) for i, t in enumerate(["KO", "PEP", "SPY"])}
    fake = FakeDownloader(frames)
    store = SnapshotStore(tmp_path / "data", repo_root=REPO_ROOT)
    src = YFinancePrices(
        store, study=STUDY, downloader=fake, clock=Clock(), pause_s=2.5,
        sleep=pauses.append,
    )
    entries = src.fetch_many(["ko", "pep", "spy"], start="2010-01-01", end="2020-01-01")
    assert [e.key for e in entries] == ["KO", "PEP", "SPY"]
    assert pauses == [2.5, 2.5]
    assert [c[0] for c in fake.calls] == ["KO", "PEP", "SPY"]


# Load ---------------------------------------------------------------------------


def _loaded_source(tmp_path: Path, n: int = 400) -> tuple[YFinancePrices, pd.DataFrame]:
    div = np.zeros(n)
    div[60::63] = 0.35
    splits = np.zeros(n)
    splits[150] = 2.0
    raw = yahoo_frame(walk(n, seed=3), dividends=div, splits=splits, start="2014-01-01")
    src, _ = source(tmp_path, {"KO": raw})
    src.fetch(PriceRequest("KO", "2010-01-01", "2020-01-01"))
    return src, raw


def test_load_returns_window_with_total_return_and_no_adj_close(tmp_path: Path) -> None:
    src, raw = _loaded_source(tmp_path)
    dates = raw.index.tz_localize(None)
    start, asof = dates[50], dates[300]
    out = src.load("ko", asof=asof, start=start)
    assert list(out.columns) == list(LOAD_COLUMNS) and "adj_close" not in out.columns
    assert out.index[0] == start and out.index[-1] == dates[299]
    assert out.attrs["ticker"] == "KO"
    assert out.attrs["snapshot_id"] == src.store.manifest.latest("yfinance", "KO").snapshot_id
    full = normalise_yfinance(raw, "KO")
    tr = total_return_index(full["close"], full["dividends"], full["capital_gains"])
    np.testing.assert_allclose(out["tr_close"], tr.iloc[50:300], rtol=0, atol=1e-9)


def test_total_return_base_does_not_depend_on_start(tmp_path: Path) -> None:
    src, raw = _loaded_source(tmp_path)
    dates = raw.index.tz_localize(None)
    whole = src.load("KO", asof=dates[300])
    later = src.load("KO", asof=dates[300], start=dates[200])
    pd.testing.assert_series_equal(later["tr_close"], whole["tr_close"].loc[dates[200]:])


def test_load_ignores_rows_at_or_after_asof(tmp_path: Path) -> None:
    """Look-ahead test: a second snapshot differs only on and after asof,
    including a NaN close, a negative dividend and a new split. Loading either
    snapshot at that asof must give identical output and must not raise."""
    src, raw = _loaded_source(tmp_path)
    cut = 300
    asof = raw.index.tz_localize(None)[cut]
    before = src.load("KO", asof=asof)
    changed = raw.copy()
    changed.iloc[cut:, changed.columns.get_loc("Close")] *= 5.0
    changed.iloc[cut + 2, changed.columns.get_loc("Close")] = np.nan
    changed.iloc[cut + 3, changed.columns.get_loc("Dividends")] = -1.0
    changed.iloc[cut + 4, changed.columns.get_loc("Stock Splits")] = 4.0
    src.downloader = FakeDownloader({"KO": changed})
    second = src.fetch(PriceRequest("KO", "2010-01-01", "2020-01-01"))
    after = src.load("KO", asof=asof, snapshot_id=second.snapshot_id)
    pd.testing.assert_frame_equal(after, before, check_exact=True)
    assert after.attrs["snapshot_id"] == second.snapshot_id != before.attrs["snapshot_id"]


def test_load_excludes_the_asof_row(tmp_path: Path) -> None:
    src, raw = _loaded_source(tmp_path)
    asof = raw.index.tz_localize(None)[300]
    assert asof not in src.load("KO", asof=asof).index


def test_load_refuses_the_locked_test_period(tmp_path: Path) -> None:
    src, _ = _loaded_source(tmp_path)
    with pytest.raises(LockedPeriodError):
        src.load("KO", asof="2022-06-01")


def test_load_drops_test_period_rows_already_in_a_snapshot(tmp_path: Path) -> None:
    """A snapshot written without the fetch guard (for example by an older
    version) may hold 2022 rows; load must still never return them."""
    store = SnapshotStore(tmp_path / "data", repo_root=REPO_ROOT)
    raw = yahoo_frame(walk(40), start="2021-12-01")
    store.write(
        source="yfinance", source_version="1.8.0", kind="prices_daily", key="KO",
        url="u", request={}, frame=raw, retrieved_at=T0,
    )
    src = YFinancePrices(store, study=STUDY, downloader=FakeDownloader({}))
    out = src.load("KO", asof=TEST_START)
    assert out.index.max() == pd.Timestamp("2021-12-31")


def test_load_in_a_fresh_clone_says_to_fetch(tmp_path: Path) -> None:
    src, _ = _loaded_source(tmp_path)
    entry = src.store.manifest.latest("yfinance", "KO")
    (src.store.root / entry.path).unlink()
    with pytest.raises(SnapshotMissingError) as info:
        src.load("KO", asof="2015-06-01")
    message = str(info.value)
    assert "KO" in message and entry.snapshot_id in message
    assert "statarb fetch KO" in message


def test_load_uncached_ticker(tmp_path: Path) -> None:
    src, _ = _loaded_source(tmp_path)
    with pytest.raises(NotCachedError, match="PEP"):
        src.load("PEP", asof="2015-06-01")


def test_load_snapshot_selection(tmp_path: Path) -> None:
    src, raw = _loaded_source(tmp_path)
    first = src.store.manifest.latest("yfinance", "KO")
    src.downloader = FakeDownloader({"KO": raw, "PEP": raw})
    second = src.fetch(PriceRequest("KO", "2010-01-01", "2020-01-01"))
    pep = src.fetch(PriceRequest("PEP", "2010-01-01", "2020-01-01"))
    asof = "2015-01-01"
    assert src.load("KO", asof=asof).attrs["snapshot_id"] == second.snapshot_id
    assert (
        src.load("KO", asof=asof, snapshot_id=first.snapshot_id).attrs["snapshot_id"]
        == first.snapshot_id
    )
    with pytest.raises(ValueError, match="is not yfinance data for KO"):
        src.load("KO", asof=asof, snapshot_id=pep.snapshot_id)


def test_load_with_no_rows_before_asof_raises(tmp_path: Path) -> None:
    src, _ = _loaded_source(tmp_path)
    with pytest.raises(ValueError, match="no rows before"):
        src.load("KO", asof="2013-01-01")


def test_fetch_converts_to_parquet_safe_types_and_notes_it(tmp_path: Path) -> None:
    """The first live run failed because the stored frame did not survive the
    Parquet round trip. Whatever dtypes the source sends, fetch must store a
    frame that does, with the same values, and record each conversion."""
    raw = yahoo_frame(walk(30), splits=np.r_[np.zeros(20), 2.0, np.zeros(9)])
    raw.index = raw.index.as_unit("s")  # Parquet would read this back as [ms]
    raw["Stock Splits"] = raw["Stock Splits"].astype(object)
    raw["Volume"] = raw["Volume"].astype("float64")
    src, _ = source(tmp_path, {"KO": raw})
    entry = src.fetch(PriceRequest("KO", "2010-01-01", "2020-01-01"))
    assert any("index converted" in n for n in entry.notes)
    assert any("Stock Splits converted from object" in n for n in entry.notes)
    assert any("Volume converted from float64" in n for n in entry.notes)
    stored = src.store.read(entry)
    np.testing.assert_array_equal(stored["Close"].to_numpy(), raw["Close"].to_numpy())
    np.testing.assert_array_equal(
        stored.index.tz_localize(None).to_numpy(),
        raw.index.tz_localize(None).as_unit("us").to_numpy(),
    )
    assert len(src.load("KO", asof="2020-01-01")) == 30


def test_fetch_refuses_a_conversion_that_changes_values(tmp_path: Path) -> None:
    raw = yahoo_frame(walk(10))
    raw["Volume"] = raw["Volume"].astype("float64") + 0.5
    src, _ = source(tmp_path, {"KO": raw})
    with pytest.raises(ValueError, match="would change values"):
        src.fetch(PriceRequest("KO", "2010-01-01", "2020-01-01"))
    assert src.store.manifest.entries() == []

"""Daily prices from yfinance, cached as immutable snapshots.

What is stored: Yahoo's output as delivered by Ticker.history with
auto_adjust=False, back_adjust=False, actions=True, repair=False, keepna=False,
rounding=False, prepost=False, interval "1d". Columns Open, High, Low, Close,
Adj Close, Volume, Dividends, Stock Splits, and Capital Gains for funds and
ETFs. The index is tz-aware exchange time. Nothing is repaired; anomalies are
flagged by the data checks, never fixed.

What signals use: `tr_close`, a forward-accumulated total-return index computed
here from Close, Dividends and Capital Gains of one snapshot:

    tr_close[0] = close[0]
    tr_close[t] = tr_close[t-1] * (close[t] + div[t] + cap_gain[t]) / close[t-1]

Row t depends only on rows up to t, so a dividend paid later never revises it.
This assumes Close and the distributions are on the same split basis (the
network test checks this on a ticker with a split).

Adjustment caveat: Yahoo's Close is assumed split-adjusted as of the download
date, so a split after asof rescales every row before asof by the same
factor. In log prices that is a constant shift: the OLS intercept moves, while
the hedge ratio, residuals and tests do not. Yahoo's Adj Close also embeds later
dividends; it is kept in the snapshot for a cross-check only and is not
returned by `load`.
"""

from __future__ import annotations

import importlib.metadata
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Final

import numpy as np
import pandas as pd

from statarb_agent.sources.base import ManifestEntry, SnapshotStore
from statarb_agent.sources.tickers import normalise_ticker
from statarb_agent.stats._asof import rows_before
from statarb_agent.study import (
    StudyConfig,
    clip_end_to_open_period,
    drop_locked_rows,
    require_before_test_period,
    to_date,
)

SOURCE: Final = "yfinance"
KIND: Final = "prices_daily"
CHART_URL: Final = "https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"

YAHOO_COLUMNS: Final = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
    "Dividends": "dividends",
    "Stock Splits": "splits",
}
YAHOO_OPTIONAL: Final = {"Capital Gains": "capital_gains"}
HISTORY_KWARGS: Final = {
    "interval": "1d",
    "auto_adjust": False,
    "back_adjust": False,
    "actions": True,
    "repair": False,
    "keepna": False,
    "rounding": False,
    "prepost": False,
}
LOAD_COLUMNS: Final = (
    "open",
    "high",
    "low",
    "close",
    "volume",
    "dividends",
    "splits",
    "capital_gains",
    "tr_close",
)

type Downloader = Callable[[str, str, str], pd.DataFrame]


class DownloadError(RuntimeError):
    """The source returned no usable data for a ticker."""


@dataclass(frozen=True)
class PriceRequest:
    """One download request. `end` is exclusive, as in yfinance."""

    ticker: str
    start: str
    end: str


def make_yfinance_downloader(cache_dir: Path, *, timeout: float = 30.0) -> Downloader:
    """Return a downloader that calls yfinance. This is the only network call.

    yfinance's timezone cache is pointed at `cache_dir` so it stays inside the
    project. Exceptions are raised rather than logged, by switching
    yf.config.debug.hide_exceptions off for the call and restoring it after
    (the raise_errors argument is deprecated in yfinance 1.8.0).
    """

    def download(ticker: str, start: str, end: str) -> pd.DataFrame:
        import yfinance as yf

        cache_dir.mkdir(parents=True, exist_ok=True)
        yf.set_tz_cache_location(str(cache_dir))
        previous = yf.config.debug.hide_exceptions
        yf.config.debug.hide_exceptions = False
        try:
            return yf.Ticker(ticker).history(
                start=start, end=end, timeout=timeout, **HISTORY_KWARGS
            )
        finally:
            yf.config.debug.hide_exceptions = previous

    return download


def normalise_yfinance(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Rename Yahoo's columns and convert the index to timezone-naive dates.

    Returns columns open, high, low, close, adj_close, volume, dividends,
    splits, capital_gains (0.0 when Yahoo sends none), in that order, on an
    index named "date". Splits are Yahoo's ratios, 0.0 on days without one.

    This checks structure only. Values are checked by check_price_values, which
    `load` runs on the rows before asof alone, so a bad row after asof cannot
    change the result.

    Raises:
        ValueError: On missing or unexpected columns, or a timestamp that is
            not midnight exchange time.
    """
    expected = set(YAHOO_COLUMNS)
    allowed = expected | set(YAHOO_OPTIONAL)
    columns = set(frame.columns)
    if not expected <= columns or not columns <= allowed:
        raise ValueError(
            f"{ticker}: unexpected yfinance columns {sorted(map(str, columns))}; "
            f"expected {sorted(expected)} plus optionally {sorted(YAHOO_OPTIONAL)}"
        )
    index = frame.index
    if not isinstance(index, pd.DatetimeIndex) or index.tz is None:
        raise ValueError(f"{ticker}: expected a timezone-aware DatetimeIndex")
    local = index.tz_localize(None)
    if not (local == local.normalize()).all():
        raise ValueError(f"{ticker}: daily bars must be stamped at midnight local time")
    out = frame.rename(columns=YAHOO_COLUMNS | YAHOO_OPTIONAL)
    if "capital_gains" not in out.columns:
        out = out.assign(capital_gains=0.0)
    out = out[[*YAHOO_COLUMNS.values(), "capital_gains"]].astype(
        {c: "float64" for c in out.columns if c != "volume"}
    )
    out.index = pd.DatetimeIndex(local, name="date", freq=None)
    return out


def canonical_yahoo_frame(
    raw: pd.DataFrame, ticker: str
) -> tuple[pd.DataFrame, list[str]]:
    """Convert a yfinance frame to types that survive a Parquet round trip.

    Price and action columns become float64, Volume int64, and the index a
    microsecond-unit DatetimeIndex with no freq. Column names and values are
    kept; a conversion that would change any value is refused. Each conversion
    made is described in the returned notes, which go into the manifest.

    Raises:
        ValueError: If a column cannot be converted without changing a value
            (for example a fractional volume).
    """
    out = raw.copy()
    notes: list[str] = []
    for col in out.columns:
        target = "int64" if col == "Volume" else "float64"
        if out[col].dtype == target:
            continue
        converted = pd.to_numeric(out[col], errors="raise").astype(target)
        same = np.array_equal(
            converted.to_numpy(dtype=float), out[col].to_numpy(dtype=float), equal_nan=True
        )
        if not same:
            raise ValueError(
                f"{ticker}: converting {col} from {out[col].dtype} to {target} would "
                "change values"
            )
        notes.append(f"{col} converted from {out[col].dtype} to {target}")
        out[col] = converted
    index = pd.DatetimeIndex(out.index)
    if index.unit != "us":
        notes.append(f"index converted from {index.dtype} to microsecond unit")
        index = index.as_unit("us")
    out.index = pd.DatetimeIndex(index, name=raw.index.name, freq=None)
    return out, notes


def check_price_values(frame: pd.DataFrame, ticker: str) -> None:
    """Refuse values the total-return index cannot use.

    Raises:
        ValueError: On duplicate or unsorted dates, a close that is missing or
            not positive, or a distribution that is missing or negative.
    """
    if not (frame.index.is_monotonic_increasing and frame.index.is_unique):
        raise ValueError(f"{ticker}: dates must be strictly increasing")
    bad = frame.index[~(frame["close"] > 0)]  # catches NaN as well
    if len(bad):
        raise ValueError(
            f"{ticker}: missing or non-positive close on {len(bad)} dates, first "
            f"{bad[0].date()}"
        )
    paid = frame["dividends"] + frame["capital_gains"]
    bad = frame.index[~(paid >= 0)]
    if len(bad):
        raise ValueError(
            f"{ticker}: missing or negative distribution on {len(bad)} dates, first "
            f"{bad[0].date()}"
        )


def total_return_index(
    close: pd.Series, dividends: pd.Series, capital_gains: pd.Series | None = None
) -> pd.Series:
    """Forward-accumulated total-return index; see the module docstring.

    Row t depends only on rows up to t. Distributions on the first row are
    ignored, because there is no previous close to measure them against.

    Raises:
        ValueError: If the inputs have different indexes, a close is missing
            or not positive, or a distribution is missing or negative.
    """
    gains = pd.Series(0.0, index=close.index) if capital_gains is None else capital_gains
    if not (close.index.equals(dividends.index) and close.index.equals(gains.index)):
        raise ValueError("close, dividends and capital gains must share one index")
    c = close.to_numpy(dtype=float)
    d = dividends.to_numpy(dtype=float) + gains.to_numpy(dtype=float)
    if not (c > 0).all():
        raise ValueError("close must be positive and not missing")
    if not (d >= 0).all():
        raise ValueError("distributions must be non-negative and not missing")
    growth = np.ones_like(c)
    growth[1:] = (c[1:] + d[1:]) / c[:-1]
    return pd.Series(c[0] * np.cumprod(growth), index=close.index, name="tr_close")


def unadjusted_close(close: pd.Series, splits: pd.Series) -> pd.Series:
    """Undo Yahoo's split adjustment: close[t] times every split ratio after t.

    The result is the price as traded on day t. It reads splits after t, so it
    is a reconstruction for display and checks, never an input to estimators,
    and `load` does not return it. Ratios of 0 mean no split.
    """
    if not close.index.equals(splits.index):
        raise ValueError("close and splits must share one index")
    ratio = splits.to_numpy(dtype=float)
    ratio = np.where(ratio == 0.0, 1.0, ratio)
    if not (ratio > 0).all():
        raise ValueError("split ratios must be positive")
    after = np.ones_like(ratio)
    after[:-1] = np.cumprod(ratio[::-1])[::-1][1:]  # product over later rows
    return pd.Series(close.to_numpy(dtype=float) * after, index=close.index,
                     name="unadjusted_close")


@dataclass(frozen=True)
class TotalReturnGap:
    """How far our total-return index drifts from Yahoo's Adj Close.

    Attributes:
        max_abs_daily_log_diff: Largest absolute difference between the two
            daily log returns.
        worst_date: Date of that difference.
        log_ratio_range: max minus min of log(tr_close / adj_close) over the
            snapshot; 0 if the two differ only by a constant factor.
    """

    max_abs_daily_log_diff: float
    worst_date: pd.Timestamp
    log_ratio_range: float


def total_return_gap(frame: pd.DataFrame) -> TotalReturnGap:
    """Compare tr_close with adj_close on a normalised snapshot (diagnostic)."""
    tr = total_return_index(frame["close"], frame["dividends"], frame["capital_gains"])
    log_ratio = np.log(tr.to_numpy()) - np.log(frame["adj_close"].to_numpy(dtype=float))
    daily = np.abs(np.diff(log_ratio))
    worst = int(np.argmax(daily))
    return TotalReturnGap(
        max_abs_daily_log_diff=float(daily[worst]),
        worst_date=frame.index[worst + 1],
        log_ratio_range=float(log_ratio.max() - log_ratio.min()),
    )


def split_day_returns(frame: pd.DataFrame) -> pd.DataFrame:
    """Simple returns of close and tr_close on each split date (diagnostic).

    If Close is split-adjusted, neither return shows the split ratio. A split
    on the first row is skipped, because it has no previous close.

    Returns:
        DataFrame indexed by split date with columns ratio, close_return and
        tr_return. Empty if the snapshot has no split.
    """
    tr = total_return_index(frame["close"], frame["dividends"], frame["capital_gains"])
    close_ret = frame["close"].pct_change()
    tr_ret = tr.pct_change()
    days = frame.index[(frame["splits"] != 0.0).to_numpy()]
    days = days[days > frame.index[0]]
    return pd.DataFrame(
        {
            "ratio": frame.loc[days, "splits"],
            "close_return": close_ret.loc[days],
            "tr_return": tr_ret.loc[days],
        },
        index=pd.DatetimeIndex(days, name="date"),
    )


def distribution_yields(frame: pd.DataFrame) -> pd.Series:
    """Each payment (dividend plus capital gain) divided by the previous close.

    Only rows with a payment are returned. A payment on the first row is
    skipped, because it has no previous close.
    """
    paid = frame["dividends"] + frame["capital_gains"]
    ratio = paid / frame["close"].shift(1)
    mask = (paid > 0).to_numpy().copy()
    mask[0] = False
    return ratio.loc[mask].rename("yield_on_previous_close")


class YFinancePrices:
    """Price source backed by yfinance and a SnapshotStore.

    `fetch` is the only method that downloads. `load` reads one snapshot from
    the cache and returns rows in [start, asof).
    """

    name: ClassVar[str] = SOURCE

    def __init__(
        self,
        store: SnapshotStore,
        *,
        study: StudyConfig,
        downloader: Downloader | None = None,
        clock: Callable[[], pd.Timestamp] | None = None,
        pause_s: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.store = store
        self.study = study
        self.downloader = downloader or make_yfinance_downloader(
            store.root / "cache" / SOURCE
        )
        self.clock = clock or (lambda: pd.Timestamp.now(tz="UTC"))
        self.pause_s = pause_s
        self.sleep = sleep

    @property
    def _repo_root(self) -> Path:
        return self.store.repo_root

    def fetch(self, request: PriceRequest) -> ManifestEntry:
        """Download one ticker and store it as a new snapshot.

        While the test period is locked, the end date is clipped to it and any
        row Yahoo still returns on or after it is dropped before storing, so
        no test-period data reaches the disk.

        Raises:
            ValueError: On an invalid ticker, or start not before the end.
            DownloadError: If the source returns nothing.
        """
        ticker = normalise_ticker(request.ticker)
        start = to_date(request.start)
        requested_end = to_date(request.end)
        end = clip_end_to_open_period(requested_end, self.study, self._repo_root)
        if not start < end:
            raise ValueError(f"start {start.date()} must be before end {end.date()}")
        notes: list[str] = []
        if end < requested_end:
            notes.append(
                f"end clipped from {requested_end.date()} to {end.date()} by the "
                "test-period lock"
            )
        retrieved_at = self.clock()
        raw = self.downloader(ticker, str(start.date()), str(end.date()))
        if raw is None or raw.empty:
            raise DownloadError(
                f"No price data for {ticker}. It may be delisted or mistyped. Free "
                "data covers only tickers that still trade (survivorship bias)."
            )
        normalise_yfinance(raw, ticker)  # refuse a malformed response before storing
        raw, conversions = canonical_yahoo_frame(raw, ticker)
        notes.extend(conversions)
        dates = raw.index.tz_localize(None)
        keep = pd.Series(dates < end, index=raw.index)
        if not keep.all():
            notes.append(f"dropped {int((~keep).sum())} rows on or after {end.date()}")
            raw = raw.loc[keep.to_numpy()]
        request_record = {
            "ticker": ticker,
            "start": str(start.date()),
            "end": str(end.date()),
            "requested_end": str(requested_end.date()),
            **HISTORY_KWARGS,
        }
        return self.store.write(
            source=SOURCE,
            source_version=importlib.metadata.version("yfinance"),
            kind=KIND,
            key=ticker,
            url=CHART_URL.format(ticker=ticker),
            request=request_record,
            frame=raw,
            retrieved_at=retrieved_at,
            notes=tuple(notes),
        )

    def fetch_many(
        self, tickers: Iterable[str], *, start: str, end: str
    ) -> list[ManifestEntry]:
        """Fetch tickers one at a time, pausing `pause_s` seconds between them."""
        entries: list[ManifestEntry] = []
        for i, ticker in enumerate(tickers):
            if i:
                self.sleep(self.pause_s)
            entries.append(self.fetch(PriceRequest(ticker, start, end)))
        return entries

    def entry_for(self, key: str, snapshot_id: str | None = None) -> ManifestEntry:
        """Manifest entry to read: the given snapshot, or the latest for `key`."""
        ticker = normalise_ticker(key)
        if snapshot_id is None:
            return self.store.manifest.latest(SOURCE, ticker)
        entry = self.store.manifest.get(snapshot_id)
        if entry.source != SOURCE or entry.key != ticker:
            raise ValueError(f"snapshot {snapshot_id} is not {SOURCE} data for {ticker}")
        return entry

    def load(
        self,
        key: str,
        *,
        asof: pd.Timestamp | str,
        start: pd.Timestamp | str | None = None,
        snapshot_id: str | None = None,
    ) -> pd.DataFrame:
        """Rows of one snapshot dated in [start, asof), with tr_close.

        Returns the columns in LOAD_COLUMNS. Adj Close is not returned (see the
        module docstring). The result's attrs hold the snapshot_id.

        Raises:
            LockedPeriodError: If asof is in the locked test period.
            NotCachedError: If no snapshot exists; SnapshotMissingError if the
                manifest lists one whose file is missing.
            CacheIntegrityError: If the file fails a hash check.
            ValueError: On an invalid ticker, or for any reason rows_before
                raises (no rows in the window, NaN, infinity).
        """
        cutoff = require_before_test_period(asof, self.study, self._repo_root)
        entry = self.entry_for(key, snapshot_id)
        frame = normalise_yfinance(self.store.read(entry), entry.key)
        frame = drop_locked_rows(frame, self.study, self._repo_root)
        # Cut at asof before any value check or computation, so rows on or
        # after asof are never read.
        frame = frame.loc[frame.index < cutoff]
        if frame.empty:
            raise ValueError(f"{entry.key}: no rows before {cutoff.date()}")
        check_price_values(frame, entry.key)
        frame = frame.assign(
            tr_close=total_return_index(
                frame["close"], frame["dividends"], frame["capital_gains"]
            )
        )
        if start is not None:
            frame = frame.loc[frame.index >= to_date(start)]
        out = rows_before(frame[list(LOAD_COLUMNS)], cutoff)
        out.attrs = {"snapshot_id": entry.snapshot_id, "ticker": entry.key}
        return out

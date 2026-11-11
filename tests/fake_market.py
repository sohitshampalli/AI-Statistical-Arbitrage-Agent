"""A fake market for end-to-end tests: frames shaped like yfinance output.

Not a test module. The end-to-end tests of the analysis path, the backtest
runner and the CLI share these helpers. Nothing here touches the network.

AAA and BBB are a simulated cointegrated pair (true hedge ratio 1.5, half-life
10); AAA pays a dividend each quarter. Every other ticker is an independent
random walk, with a few built to fail or flag a data check.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from statarb_agent.data.synthetic import simulate_cointegrated_pair
from statarb_agent.project import Project

REPO_ROOT = Path(__file__).resolve().parents[1]
CALENDAR = pd.bdate_range("2010-01-04", "2021-12-31", tz="America/New_York", name="Date")
ASOF = pd.Timestamp("2018-01-01")  # formation as-of; a Monday, so a row has this date
N_FORMATION = int((CALENDAR.tz_localize(None) < ASOF).sum())
DEMO_TICKERS = ("V", "MA", "KO", "PEP", "XOM", "CVX", "HD", "LOW", "EWA", "EWC")
BASKET_EXTRA = ("KDP",)


def frame_from_close(close: np.ndarray, dividends: np.ndarray | None = None) -> pd.DataFrame:
    """A frame shaped like Ticker.history(auto_adjust=False, actions=True)."""
    n = len(close)
    div = np.zeros(n) if dividends is None else dividends
    return pd.DataFrame(
        {
            "Open": close, "High": close * 1.01, "Low": close * 0.99, "Close": close,
            "Adj Close": close, "Volume": np.full(n, 1000, dtype="int64"),
            "Dividends": div, "Stock Splits": np.zeros(n),
        },
        index=CALENDAR[:n] if n <= len(CALENDAR) else None,
    )


def walk(seed: int, start: float = 80.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return start * np.exp(np.cumsum(0.01 * rng.standard_normal(len(CALENDAR))))


def base_frames() -> dict[str, pd.DataFrame]:
    """AAA and BBB are cointegrated (beta 1.5, half-life 10); the rest are walks."""
    pair = simulate_cointegrated_pair(seed=11, n_obs=len(CALENDAR))
    dividends = np.zeros(len(CALENDAR))
    dividends[40::63] = 0.25
    frames = {
        "AAA": frame_from_close(np.exp(pair["log_a"].to_numpy()), dividends),
        "BBB": frame_from_close(np.exp(pair["log_b"].to_numpy())),
        "SPY": frame_from_close(walk(1, 200.0)),
    }
    for i, ticker in enumerate((*DEMO_TICKERS, *BASKET_EXTRA)):
        frames[ticker] = frame_from_close(walk(100 + i))
    gap = frame_from_close(walk(3))
    frames["GAP"] = gap.drop(gap.index[[300, 301, 950]])
    late = frame_from_close(walk(4))
    frames["LATE"] = late.loc[late.index >= "2012-06-01"]
    big = np.zeros(len(CALENDAR))
    big[500] = 0.3 * walk(5)[499]
    frames["BIGDIV"] = frame_from_close(walk(5), big)
    frames["NODATA"] = frame_from_close(walk(6)).iloc[:0]
    return frames


class FakeDownloader:
    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self.frames = frames
        self.calls: list[tuple[str, str, str]] = []

    def __call__(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        self.calls.append((ticker, start, end))
        return self.frames[ticker].copy()




def make_project(tmp_path: Path, *, small_controls: bool = False) -> Project:
    """A throwaway project folder with the repository's configs and no pause.

    With small_controls the control batches and placebos use 3 seeds and the
    simulated controls 800 rows, so a full demo backtest runs in seconds. The
    strategy settings are the repository's.
    """
    root = tmp_path / "project"
    shutil.copytree(REPO_ROOT / "configs", root / "configs")
    path = root / "configs" / "data.yaml"
    path.write_text(path.read_text().replace("pause_seconds: 2.0", "pause_seconds: 0.0"))
    if small_controls:
        path = root / "configs" / "backtest.yaml"
        text = path.read_text()
        for old, new in (
            ("  batch_size: 200", "  batch_size: 3"),
            ("  placebo_shuffles: 200", "  placebo_shuffles: 3"),
            ("  n_obs: 3130", "  n_obs: 800"),
        ):
            assert text.count(old) == 1, old
            text = text.replace(old, new)
        path.write_text(text)
    return Project(root)

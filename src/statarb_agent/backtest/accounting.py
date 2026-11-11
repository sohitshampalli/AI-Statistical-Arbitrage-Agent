"""Daily accounting for a long-short position in two or more assets.

This module turns position decisions into a ledger. It knows nothing about
statistics: it takes prices, cash distributions, and the decision made after
each bar, and it books profit, costs and exposure day by day.

Timing (the rule that prevents look-ahead):

- The decision of bar t is made after bar t's close, from data up to bar t.
- It is executed at the close of bar t + 1, never on bar t.
- A position opened at the close of bar t + 1 first earns the move from t + 1
  to t + 2.

So the ledger row of bar t depends on prices up to bar t and decisions up to
bar t - 1. The decision of the last bar is never executed.

What is booked on bar t, for the shares held since the close of bar t - 1:

- price_pnl: shares times (close[t] - close[t-1]).
- dist_pnl: shares times the cash distribution with ex-date t (dividends and
  capital gains). A long position receives it; a short position owes it.
- borrow_cost: the value of the short positions at the close of t - 1, times
  the annual borrow fee, times calendar days since bar t - 1 over the day count.
- trade_cost: if an order executes at this close, the traded value of every
  leg times the cost in basis points.

Sizing: an entry puts `capital * gross_exposure` to work, split across the legs
by the dollar weights given with the decision (their absolute values sum to
1). Shares are fixed from entry to exit; there is no rebalancing in between.
Sizing always uses the initial capital, so profits are not reinvested.

Cash earns no interest and short-sale proceeds are simply held as cash.

Identity checked in the tests: equity = cash + market value of the shares, and
the day's pnl is the change in equity.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

BPS = 1e-4


@dataclass(frozen=True)
class CostModel:
    """Trading and financing costs.

    Attributes:
        cost_bps_per_leg: Spread and slippage, in basis points of the traded
            value of each leg, charged on every execution.
        borrow_fee_bps_annual: Annual fee on the value of short positions.
        borrow_day_count: Days in the fee's year (360 by market convention).
    """

    cost_bps_per_leg: float
    borrow_fee_bps_annual: float
    borrow_day_count: int = 360

    def __post_init__(self) -> None:
        for name in ("cost_bps_per_leg", "borrow_fee_bps_annual"):
            value = getattr(self, name)
            if not (math.isfinite(value) and value >= 0.0):
                raise ValueError(f"{name} must be finite and >= 0, got {value!r}")
        if self.borrow_day_count not in (360, 365):
            raise ValueError("borrow_day_count must be 360 or 365")


@dataclass(frozen=True)
class Ledger:
    """Output of simulate_ledger.

    Attributes:
        daily: One row per bar; columns are listed in simulate_ledger.
        trades: One row per trade, closed or still open at the last bar.
    """

    daily: pd.DataFrame
    trades: pd.DataFrame


TRADE_COLUMNS = (
    "trade_id", "side", "entry_signal_date", "entry_date", "exit_signal_date",
    "exit_date", "exit_reason", "bars_held", "entry_z", "exit_z", "price_pnl",
    "dist_pnl", "borrow_cost", "trade_cost", "net_pnl", "open",
)


def simulate_ledger(
    index: pd.DatetimeIndex,
    close: np.ndarray,
    distributions: np.ndarray,
    target: np.ndarray,
    dollar_weights: np.ndarray,
    *,
    labels: tuple[str, ...],
    capital: float,
    gross_exposure: float,
    costs: CostModel,
    reasons: np.ndarray | None = None,
    z: np.ndarray | None = None,
) -> Ledger:
    """Book the decisions in `target` against prices, one bar after each decision.

    Args:
        index: Dates of the bars, strictly increasing.
        close: Close price per bar and asset, shape (n, k), all positive.
        distributions: Cash per share with ex-date on that bar, shape (n, k).
        target: Decision after each bar: +1 long the spread, -1 short, 0 flat.
        dollar_weights: Shape (n, k). Row t gives the dollar split of one unit
            long the spread if an entry is decided at bar t: positive for
            legs bought, negative for legs sold short, absolute sum 1. Only
            rows where an entry is decided are read.
        labels: Asset names, used in column names.
        capital: Initial capital, > 0.
        gross_exposure: Fraction of capital put to work at entry, summed over
            the legs in absolute value.
        costs: Cost model.
        reasons: Optional text per bar explaining the decision (for the trade
            list).
        z: Optional z-score per bar (for the trade list).

    Returns:
        Ledger. `daily` is indexed by `index` with columns:
        position (after this bar's execution), decision (target of this bar),
        price_pnl, dist_pnl, borrow_cost, trade_cost, gross_pnl (price plus
        distributions), pnl (gross minus both costs), ret and gross_ret (over
        capital), equity, cash, gross_exposure, net_exposure (both in currency
        after execution), traded_notional, and shares_<label> per asset.
        `trades` has the columns in TRADE_COLUMNS plus notional_<label>, the
        signed entry value of each leg. Dates of an open trade's exit are NaT.

    Raises:
        ValueError: On inconsistent shapes, non-positive or non-finite prices,
            negative distributions, a target outside {-1, 0, 1}, or entry
            weights that are not finite with absolute sum 1.
    """
    n = len(index)
    close = np.asarray(close, dtype=float)
    distributions = np.asarray(distributions, dtype=float)
    target = np.asarray(target)
    dollar_weights = np.asarray(dollar_weights, dtype=float)
    k = len(labels)
    if close.shape != (n, k) or distributions.shape != (n, k):
        raise ValueError(f"close and distributions must have shape ({n}, {k})")
    if dollar_weights.shape != (n, k) or target.shape != (n,):
        raise ValueError("target and dollar_weights do not match the number of bars")
    if not isinstance(index, pd.DatetimeIndex) or not (
        index.is_monotonic_increasing and index.is_unique
    ):
        raise ValueError("index must be a strictly increasing DatetimeIndex")
    if not (np.isfinite(close).all() and (close > 0.0).all()):
        raise ValueError("close prices must be finite and positive")
    if not (np.isfinite(distributions).all() and (distributions >= 0.0).all()):
        raise ValueError("distributions must be finite and >= 0")
    if not np.isin(target, (-1, 0, 1)).all():
        raise ValueError("target must contain only -1, 0 and 1")
    if not (math.isfinite(capital) and capital > 0.0):
        raise ValueError("capital must be finite and > 0")
    if not (math.isfinite(gross_exposure) and gross_exposure > 0.0):
        raise ValueError("gross_exposure must be finite and > 0")
    reasons = np.full(n, "", dtype=object) if reasons is None else np.asarray(reasons)
    z = np.full(n, np.nan) if z is None else np.asarray(z, dtype=float)
    if reasons.shape != (n,) or z.shape != (n,):
        raise ValueError("reasons and z must have one entry per bar")

    days = np.zeros(n)
    if n > 1:
        days[1:] = np.diff(index.to_numpy()).astype("timedelta64[D]").astype(float)
    cost_rate = costs.cost_bps_per_leg * BPS
    borrow_rate = costs.borrow_fee_bps_annual * BPS / costs.borrow_day_count
    notional = capital * gross_exposure

    shares = np.zeros(k)
    held = 0
    cash = capital
    columns = {
        name: np.zeros(n)
        for name in (
            "price_pnl", "dist_pnl", "borrow_cost", "trade_cost", "equity", "cash",
            "gross_exposure", "net_exposure", "traded_notional",
        )
    }
    position = np.zeros(n, dtype=np.int8)
    shares_out = np.zeros((n, k))
    trades: list[dict[str, object]] = []
    current: dict[str, object] | None = None

    for t in range(n):
        if t > 0:
            price_pnl = float(shares @ (close[t] - close[t - 1]))
            dist_pnl = float(shares @ distributions[t])
            short_value = float(-(np.minimum(shares, 0.0) @ close[t - 1]))
            borrow = short_value * borrow_rate * days[t]
            trade_cost = 0.0
            traded = 0.0
            if current is not None:
                current["price_pnl"] += price_pnl
                current["dist_pnl"] += dist_pnl
                current["borrow_cost"] += borrow
            wanted = int(target[t - 1])
            if wanted != held:
                # Execute at this close the decision made after the previous bar.
                if wanted == 0:
                    new_shares = np.zeros(k)
                else:
                    weights = dollar_weights[t - 1]
                    total = np.abs(weights).sum()
                    if not (np.isfinite(weights).all() and abs(total - 1.0) < 1e-9):
                        raise ValueError(
                            f"entry decided on {index[t - 1].date()} has dollar "
                            "weights that are not finite with absolute sum 1"
                        )
                    new_shares = wanted * weights * notional / close[t]
                # A change of position is booked as closing the old shares and
                # opening the new ones, with no netting between the two, so a
                # direct reversal pays costs on both. (The z-score rule never
                # reverses in one bar; this keeps the ledger correct if a
                # caller does.)
                exit_value = float(np.abs(shares) @ close[t])
                entry_value = float(np.abs(new_shares) @ close[t])
                traded = exit_value + entry_value
                trade_cost = traded * cost_rate
                cash -= float((new_shares - shares) @ close[t])
                if current is not None:
                    current["trade_cost"] += exit_value * cost_rate
                    current.update(
                        exit_signal_date=index[t - 1], exit_date=index[t],
                        exit_reason=str(reasons[t - 1]), exit_z=float(z[t - 1]),
                        bars_held=t - current["_entry_bar"], open=False,
                    )
                    trades.append(current)
                    current = None
                if wanted != 0:
                    current = {
                        "trade_id": len(trades),
                        "side": wanted,
                        "entry_signal_date": index[t - 1],
                        "entry_date": index[t],
                        "exit_signal_date": pd.NaT,
                        "exit_date": pd.NaT,
                        "exit_reason": "",
                        "bars_held": 0,
                        "entry_z": float(z[t - 1]),
                        "exit_z": float("nan"),
                        "price_pnl": 0.0,
                        "dist_pnl": 0.0,
                        "borrow_cost": 0.0,
                        "trade_cost": entry_value * cost_rate,
                        "open": True,
                        "_entry_bar": t,
                        **{
                            f"notional_{label}": float(new_shares[i] * close[t, i])
                            for i, label in enumerate(labels)
                        },
                    }
                shares = new_shares
                held = wanted
            cash += dist_pnl - borrow - trade_cost
            columns["price_pnl"][t] = price_pnl
            columns["dist_pnl"][t] = dist_pnl
            columns["borrow_cost"][t] = borrow
            columns["trade_cost"][t] = trade_cost
            columns["traded_notional"][t] = traded
        value = shares * close[t]
        columns["cash"][t] = cash
        columns["equity"][t] = cash + float(value.sum())
        columns["gross_exposure"][t] = float(np.abs(value).sum())
        columns["net_exposure"][t] = float(value.sum())
        position[t] = held
        shares_out[t] = shares

    if current is not None:
        current["bars_held"] = n - 1 - current["_entry_bar"]
        trades.append(current)

    daily = pd.DataFrame(index=index)
    daily["position"] = position
    daily["decision"] = target.astype(np.int8)
    for name in ("price_pnl", "dist_pnl", "borrow_cost", "trade_cost"):
        daily[name] = columns[name]
    daily["gross_pnl"] = daily["price_pnl"] + daily["dist_pnl"]
    daily["pnl"] = daily["gross_pnl"] - daily["borrow_cost"] - daily["trade_cost"]
    daily["ret"] = daily["pnl"] / capital
    daily["gross_ret"] = daily["gross_pnl"] / capital
    for name in ("equity", "cash", "gross_exposure", "net_exposure", "traded_notional"):
        daily[name] = columns[name]
    for i, label in enumerate(labels):
        daily[f"shares_{label}"] = shares_out[:, i]

    notional_columns = [f"notional_{label}" for label in labels]
    frame = pd.DataFrame(trades, columns=[*TRADE_COLUMNS, "_entry_bar", *notional_columns])
    frame = frame.drop(columns="_entry_bar")
    if len(frame):
        frame["net_pnl"] = (
            frame["price_pnl"] + frame["dist_pnl"] - frame["borrow_cost"]
            - frame["trade_cost"]
        )
    frame = frame.astype(
        {
            "trade_id": "int64", "side": "int64", "bars_held": "int64", "open": "bool",
            "exit_reason": "object",
            **{
                name: "float64"
                for name in (
                    "entry_z", "exit_z", "price_pnl", "dist_pnl", "borrow_cost",
                    "trade_cost", "net_pnl", *notional_columns,
                )
            },
        }
    )
    # Give the date columns the dtype of the bar index whatever the content, so
    # an empty trade list and a full one have the same schema.
    for name in ("entry_signal_date", "entry_date", "exit_signal_date", "exit_date"):
        frame[name] = pd.to_datetime(frame[name]).astype(index.dtype)
    return Ledger(daily=daily, trades=frame)

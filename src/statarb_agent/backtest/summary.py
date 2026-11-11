"""Turn a backtest's ledger into metrics for a span of dates.

A span is a range of calendar dates, for example the formation period or the
validation period. Its metrics use the ledger rows dated inside it (and never
before the first signal bar) and the trades that closed inside it. Nothing
here estimates parameters; it only summarises rows the engine already
produced, with the tested functions in backtest.metrics.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from statarb_agent.backtest import metrics as m
from statarb_agent.backtest.engine import BacktestResult
from statarb_agent.study import StudyConfig

NAN = float("nan")


def simple_returns(tr_close: pd.Series) -> pd.Series:
    """Daily simple returns of a total-return index: tr[t] / tr[t-1] - 1.

    The first row has no return and is dropped. Row t uses rows t and t - 1.
    """
    values = tr_close.to_numpy(dtype=float)
    return pd.Series(values[1:] / values[:-1] - 1.0, index=tr_close.index[1:])


def span_metrics(
    result: BacktestResult,
    *,
    start: pd.Timestamp | str | None = None,
    end: pd.Timestamp | str | None = None,
    benchmark: pd.Series | None = None,
) -> dict[str, Any] | None:
    """Metrics of one backtest over the dates in [start, end], both inclusive.

    Args:
        result: A backtest result.
        start: First date of the span; never earlier than the first signal
            bar. None means from the first signal bar.
        end: Last date of the span. None means to the last row.
        benchmark: Daily simple returns of a benchmark (SPY) indexed by date,
            for the beta. Rows of the span missing from it make the beta NaN.

    Returns:
        A dict of plain numbers (NaN where undefined), or None if the span has
        fewer than two ledger rows. Returns are fractions of the fixed capital.
        Keys: start, end, n_days, total_return, annualised_return,
        annualised_volatility, sharpe, sharpe_per_period, gross_sharpe,
        sortino, max_drawdown, calmar, skewness, kurtosis, psr_zero, n_trades,
        hit_rate, average_holding_bars, annual_turnover, cost_drag,
        beta_to_benchmark, share_in_market, price_return, distribution_return,
        trade_cost_return, borrow_cost_return, exit_reasons.
    """
    daily = result.daily
    capital = float(result.settings["capital"])
    first = result.first_signal_date
    lo = first if start is None else max(first, pd.Timestamp(start))
    hi = daily.index[-1] if end is None else pd.Timestamp(end)
    rows = daily.loc[(daily.index >= lo) & (daily.index <= hi)]
    if len(rows) < 2:
        return None
    ret = rows["ret"].to_numpy(dtype=float)
    gross = rows["gross_ret"].to_numpy(dtype=float)
    # Equity inside the span, starting from the capital, so a loss on the
    # first day of the span counts as a drawdown.
    equity = capital * (1.0 + np.concatenate([[0.0], np.cumsum(ret)]))
    trades = result.trades
    closed = trades.loc[
        ~trades["open"] & (trades["exit_date"] >= rows.index[0])
        & (trades["exit_date"] <= rows.index[-1])
    ]
    beta = NAN
    if benchmark is not None and rows.index.isin(benchmark.index).all():
        beta = m.beta_to_benchmark(ret, benchmark.loc[rows.index].to_numpy(dtype=float))
    per_period = m.sharpe_per_period(ret)
    skew, kurt = m.skewness(ret), m.kurtosis(ret)
    try:
        drawdown = m.max_drawdown(equity)
        calmar = m.calmar_ratio(ret, equity)
    except ValueError:  # equity fell to zero or below: the capital was lost
        drawdown, calmar = 1.0, NAN
    return {
        "start": str(rows.index[0].date()),
        "end": str(rows.index[-1].date()),
        "n_days": len(rows),
        "total_return": float(ret.sum()),
        "annualised_return": m.annualised_return(ret),
        "annualised_volatility": m.annualised_volatility(ret),
        "sharpe": m.sharpe_ratio(ret),
        "sharpe_per_period": per_period,
        "gross_sharpe": m.sharpe_ratio(gross),
        "sortino": m.sortino_ratio(ret),
        "max_drawdown": drawdown,
        "calmar": calmar,
        "skewness": skew,
        "kurtosis": kurt,
        "psr_zero": m.probabilistic_sharpe_ratio(per_period, len(ret), skew, kurt),
        "n_trades": len(closed),
        "hit_rate": m.hit_rate(closed["net_pnl"].to_numpy(dtype=float)),
        "average_holding_bars": m.average_holding_period(
            closed["bars_held"].to_numpy(dtype=float)
        ),
        "annual_turnover": m.annual_turnover(
            rows["traded_notional"].to_numpy(dtype=float), capital
        ),
        "cost_drag": m.cost_drag(gross, ret),
        "beta_to_benchmark": beta,
        "share_in_market": float((rows["position"] != 0).mean()),
        "price_return": float(rows["price_pnl"].sum() / capital),
        "distribution_return": float(rows["dist_pnl"].sum() / capital),
        "trade_cost_return": float(rows["trade_cost"].sum() / capital),
        "borrow_cost_return": float(rows["borrow_cost"].sum() / capital),
        "exit_reasons": {
            str(reason): int(count)
            for reason, count in closed["exit_reason"].value_counts().sort_index().items()
        },
    }


def study_span_metrics(
    result: BacktestResult, study: StudyConfig, *, benchmark: pd.Series | None = None
) -> dict[str, dict[str, Any] | None]:
    """Metrics for the whole run, the formation period and the validation period.

    "formation" runs from the first signal bar to the end of the formation
    period; "validation" covers the validation period. The walk-forward run is
    continuous, so the first validation windows were fitted on late formation
    rows, which is still data before each window.
    """
    return {
        "full": span_metrics(result, benchmark=benchmark),
        "formation": span_metrics(result, end=study.formation.end, benchmark=benchmark),
        "validation": span_metrics(
            result, start=study.validation.start, end=study.validation.end,
            benchmark=benchmark,
        ),
    }

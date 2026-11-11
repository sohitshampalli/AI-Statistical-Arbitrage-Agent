"""Walk-forward backtest engine for a pair or a basket.

Layout of the bars (row numbers, counted from the first row of the data):

    window k forms on rows  [k * trading, k * trading + formation)
    window k trades on rows [formation + k * trading, formation + (k + 1) * trading)

With formation = 252 and trading = 63, window 0 is fitted on rows 0 to 251 and
trades rows 252 to 314; window 1 is fitted on rows 63 to 314 and trades rows
315 to 377; and so on. The layout is counted from the start, so adding later
rows never moves an earlier window.

For each trading window the parameters come from its formation rows only, which
all lie before the window's first bar:

- static:  alpha, beta and the residual standard deviation of one OLS fit on
           the formation rows, held for the whole window.
- rolling: for each bar, an OLS fit on the `formation` rows just before it.
- kalman:  a Kalman filter started from the formation OLS fit (its estimate and
           covariance), with the formation residual variance as observation
           noise and a forgetting factor; it then updates every bar. The values
           used on a bar are the forecasts made before that bar.
- basket:  the first Johansen eigenvector on the formation rows, and the mean
           and standard deviation of that combination on the same rows.

The signal on bar t is z[t] = spread[t] / sigma[t], where spread[t] uses bar
t's prices with parameters estimated before bar t. The z-score rule
(signals.zscore) turns z into a decision, and the ledger (backtest.accounting)
executes each decision at the close of the next bar. The last signal bar of
every window forces the position flat, so no position is carried into a
window with different parameters.

A pair is traded on a bar only if beta is positive there: a long-short pair
needs two legs that move together, and with beta <= 0 "long A, short B" is not
a bet on the spread. Such bars are flat and counted as not tradeable.

Signals use log total-return prices (tr_close). Profit is booked on close
prices plus the distributions, which is the same total return split into its
parts, so dividends owed on the short leg appear as their own line.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from statarb_agent.backtest.accounting import simulate_ledger
from statarb_agent.backtest.config import HEDGES, NEUTRALITIES, BacktestConfig
from statarb_agent.signals.zscore import decide_positions
from statarb_agent.stats._asof import rows_before
from statarb_agent.stats.hedge_ratio import (
    ols_hedge_ratio,
    ols_residual_sd,
    rolling_ols_hedge,
)
from statarb_agent.stats.johansen import johansen_test
from statarb_agent.stats.kalman import kalman_hedge

PRICE_COLUMNS = ("close", "dividends", "capital_gains", "tr_close")


@dataclass(frozen=True)
class BacktestResult:
    """Everything one backtest produced.

    Attributes:
        kind: "pair" or "basket".
        labels: Asset names in order.
        hedge: "static", "rolling", "kalman" or "johansen".
        cost_bps: Trading cost per leg used in this run.
        daily: The ledger, one row per bar (see accounting.simulate_ledger),
            plus the column `window`.
        trades: One row per trade.
        signals: One row per bar: window, parameters, spread, z, tradeable,
            dollar weights, decision and reason.
        windows: One row per trading window with its dates and parameters.
        first_signal_date: Date of the first bar that could carry a signal.
            Metrics are measured from this date on.
        settings: The values the run used, for the trial log.
    """

    kind: str
    labels: tuple[str, ...]
    hedge: str
    cost_bps: float
    daily: pd.DataFrame
    trades: pd.DataFrame
    signals: pd.DataFrame
    windows: pd.DataFrame
    first_signal_date: pd.Timestamp
    settings: dict[str, Any]


def window_layout(n: int, formation: int, trading: int) -> tuple[np.ndarray, np.ndarray]:
    """Window number and last-bar flag for each of n rows.

    Returns:
        (window, window_last). window[t] is -1 for the first `formation` rows
        and (t - formation) // trading after. window_last[t] is True on the
        last row of each full trading window.
    """
    rows = np.arange(n)
    offset = rows - formation
    window = np.where(offset >= 0, offset // trading, -1)
    window_last = (offset >= 0) & (offset % trading == trading - 1)
    return window, window_last


def _after(index: pd.DatetimeIndex) -> pd.Timestamp:
    """A date just after the last row, to pass as asof for 'all of these rows'."""
    return index[-1] + pd.Timedelta(days=1)


def pair_signal_frame(
    log_a: pd.Series,
    log_b: pd.Series,
    *,
    hedge: str,
    formation: int,
    trading: int,
    neutrality: str,
    kalman_discount: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parameters, spread and z for every bar of a pair, and a table of windows.

    Every value on row t is computed from rows before t, except the spread and
    z, which also use row t's own two prices.

    Args:
        log_a, log_b: Log total-return prices with identical indexes. Every
            row is used; the caller cuts at asof first.
        hedge: "static", "rolling" or "kalman".
        formation, trading: Window lengths in bars.
        neutrality: "dollar" (equal value long and short) or "beta" (values in
            proportion 1 : beta).
        kalman_discount: Forgetting factor of the Kalman variant.

    Returns:
        (signals, windows). signals has columns window, window_last, alpha,
        beta, sigma, spread, z, tradeable, weight_a, weight_b. windows has one
        row per trading window.
    """
    if hedge not in HEDGES:
        raise ValueError(f"hedge must be one of {HEDGES}, got {hedge!r}")
    if neutrality not in NEUTRALITIES:
        raise ValueError(f"neutrality must be one of {NEUTRALITIES}, got {neutrality!r}")
    if not log_a.index.equals(log_b.index):
        raise ValueError("the two legs have different indexes; align them first")
    index = pd.DatetimeIndex(log_a.index)
    n = len(index)
    y = log_a.to_numpy(dtype=float)
    x = log_b.to_numpy(dtype=float)
    window, window_last = window_layout(n, formation, trading)
    alpha = np.full(n, np.nan)
    beta = np.full(n, np.nan)
    sigma = np.full(n, np.nan)
    records: list[dict[str, Any]] = []
    n_windows = int(window.max()) + 1 if n > formation else 0

    for k in range(n_windows):
        t0 = formation + k * trading
        t1 = min(t0 + trading, n)
        lo = t0 - formation
        record: dict[str, Any] = {
            "window": k,
            "formation_start": index[lo],
            "formation_end": index[t0 - 1],
            "trade_start": index[t0],
            "trade_end": index[t1 - 1],
            "n_bars": t1 - t0,
            "alpha": np.nan,
            "beta": np.nan,
            "sigma": np.nan,
        }
        records.append(record)
        if np.ptp(x[lo:t0]) == 0.0:
            continue  # beta is not identified; the window is not tradeable
        form_a, form_b = log_a.iloc[lo:t0], log_b.iloc[lo:t0]
        # asof is the first trading bar: the fit sees the formation rows only.
        fit = ols_hedge_ratio(form_a, form_b, index[t0])
        resid_sd = ols_residual_sd(form_a, form_b, fit)
        record.update(alpha=fit.alpha, beta=fit.beta, sigma=resid_sd)
        if hedge == "static":
            alpha[t0:t1], beta[t0:t1], sigma[t0:t1] = fit.alpha, fit.beta, resid_sd
        elif hedge == "kalman" and resid_sd > 0.0:
            design = np.column_stack([np.ones(formation), x[lo:t0]])
            init_cov = resid_sd**2 * np.linalg.inv(design.T @ design)
            init_cov = (init_cov + init_cov.T) / 2.0
            path = kalman_hedge(
                log_a.iloc[t0:t1], log_b.iloc[t0:t1], _after(index[t0:t1]),
                obs_var=resid_sd**2, init_mean=np.array([fit.alpha, fit.beta]),
                init_cov=init_cov, discount=kalman_discount,
            )
            alpha[t0:t1] = path["alpha_pred"].to_numpy()
            beta[t0:t1] = path["beta_pred"].to_numpy()
            sigma[t0:t1] = np.sqrt(path["innovation_var"].to_numpy())

    if hedge == "rolling" and n > formation:
        rolling = rolling_ols_hedge(log_a, log_b, _after(index), window=formation)
        alpha[formation:] = rolling["alpha"].to_numpy()
        beta[formation:] = rolling["beta"].to_numpy()
        sigma[formation:] = rolling["resid_sd"].to_numpy()

    spread = y - alpha - beta * x
    z = np.full(n, np.nan)
    usable = np.isfinite(sigma) & (sigma > 0.0) & np.isfinite(spread)
    z[usable] = spread[usable] / sigma[usable]
    with np.errstate(invalid="ignore"):
        tradeable = (window >= 0) & np.isfinite(z) & (beta > 0.0)
    weight_a = np.full(n, np.nan)
    weight_b = np.full(n, np.nan)
    if neutrality == "dollar":
        weight_a[tradeable], weight_b[tradeable] = 0.5, -0.5
    else:
        weight_a[tradeable] = 1.0 / (1.0 + beta[tradeable])
        weight_b[tradeable] = -beta[tradeable] / (1.0 + beta[tradeable])
    signals = pd.DataFrame(
        {
            "window": window, "window_last": window_last, "alpha": alpha, "beta": beta,
            "sigma": sigma, "spread": spread, "z": z, "tradeable": tradeable,
            "weight_a": weight_a, "weight_b": weight_b,
        },
        index=index,
    )
    return signals, pd.DataFrame.from_records(records)


def basket_signal_frame(
    log_prices: pd.DataFrame,
    *,
    formation: int,
    trading: int,
    det_order: int,
    k_ar_diff: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Johansen weights, spread and z for every bar of a basket.

    For each window the first Johansen eigenvector w (absolute sum 1) is
    estimated on the formation rows. The spread is w . log prices minus its
    formation mean, and sigma is its formation standard deviation (ddof 1).
    The dollar weights of one unit long the spread are w itself.

    Returns:
        (signals, windows). signals has columns window, window_last, sigma,
        spread, z, tradeable, rank and weight_<label> per asset. windows adds
        the Johansen rank and trace statistic of each formation window.
    """
    index = pd.DatetimeIndex(log_prices.index)
    labels = [str(c) for c in log_prices.columns]
    values = log_prices.to_numpy(dtype=float)
    n, k_assets = values.shape
    window, window_last = window_layout(n, formation, trading)
    weights = np.full((n, k_assets), np.nan)
    mean = np.full(n, np.nan)
    sigma = np.full(n, np.nan)
    rank = np.full(n, -1)
    records: list[dict[str, Any]] = []
    n_windows = int(window.max()) + 1 if n > formation else 0
    for k in range(n_windows):
        t0 = formation + k * trading
        t1 = min(t0 + trading, n)
        lo = t0 - formation
        res = johansen_test(
            log_prices.iloc[lo:t0], index[t0], det_order=det_order, k_ar_diff=k_ar_diff
        )
        w = np.array(res.weights)
        combo = values[lo:t0] @ w
        weights[t0:t1] = w
        mean[t0:t1] = combo.mean()
        sigma[t0:t1] = combo.std(ddof=1)
        rank[t0:t1] = res.rank_trace
        records.append(
            {
                "window": k,
                "formation_start": index[lo],
                "formation_end": index[t0 - 1],
                "trade_start": index[t0],
                "trade_end": index[t1 - 1],
                "n_bars": t1 - t0,
                "sigma": float(combo.std(ddof=1)),
                "rank_trace": res.rank_trace,
                "trace_stat_0": res.trace_stats[0],
                "trace_crit_95_0": res.trace_crit_95[0],
                **{f"weight_{label}": float(w[i]) for i, label in enumerate(labels)},
            }
        )
    spread = np.einsum("ij,ij->i", values, np.nan_to_num(weights)) - mean
    z = np.full(n, np.nan)
    usable = np.isfinite(sigma) & (sigma > 0.0) & np.isfinite(spread)
    z[usable] = spread[usable] / sigma[usable]
    tradeable = (window >= 0) & np.isfinite(z)
    signals = pd.DataFrame(
        {
            "window": window, "window_last": window_last, "sigma": sigma,
            "spread": spread, "z": z, "tradeable": tradeable, "rank": rank,
            **{f"weight_{label}": weights[:, i] for i, label in enumerate(labels)},
        },
        index=index,
    )
    return signals, pd.DataFrame.from_records(records)


def _prepare(
    frames: dict[str, pd.DataFrame], asof: pd.Timestamp | str, config: BacktestConfig
) -> dict[str, pd.DataFrame]:
    """Cut every frame at asof and require identical dates and enough rows."""
    need = config.formation_days + 2
    cut: dict[str, pd.DataFrame] = {}
    for label, frame in frames.items():
        missing = set(PRICE_COLUMNS) - set(frame.columns)
        if missing:
            raise ValueError(f"{label} is missing the columns {sorted(missing)}")
        cut[label] = rows_before(frame[list(PRICE_COLUMNS)], asof, min_obs=need)
    first = next(iter(cut.values()))
    for label, frame in cut.items():
        if not frame.index.equals(first.index):
            raise ValueError(
                f"{label} has different dates before asof; align the legs first"
            )
        if not (frame[["close", "tr_close"]] > 0.0).all().all():
            raise ValueError(f"{label} has a non-positive price")
    return cut


def _finish(
    kind: str,
    hedge: str,
    cut: dict[str, pd.DataFrame],
    signals: pd.DataFrame,
    windows: pd.DataFrame,
    weight_columns: list[str],
    config: BacktestConfig,
    cost_bps: float | None,
) -> BacktestResult:
    labels = tuple(cut)
    index = pd.DatetimeIndex(signals.index)
    decisions = decide_positions(
        signals["z"].to_numpy(), signals["tradeable"].to_numpy(),
        signals["window_last"].to_numpy(), config.signal,
    )
    costs = config.cost_model(cost_bps)
    ledger = simulate_ledger(
        index,
        np.column_stack([cut[label]["close"].to_numpy(dtype=float) for label in labels]),
        np.column_stack(
            [
                (cut[label]["dividends"] + cut[label]["capital_gains"]).to_numpy(dtype=float)
                for label in labels
            ]
        ),
        decisions.target,
        signals[weight_columns].to_numpy(dtype=float),
        labels=labels,
        capital=config.capital,
        gross_exposure=config.gross_exposure,
        costs=costs,
        reasons=decisions.reason,
        z=signals["z"].to_numpy(),
    )
    signals = signals.assign(decision=decisions.target, reason=decisions.reason)
    daily = ledger.daily.assign(window=signals["window"].to_numpy())
    settings = {
        "kind": kind,
        "hedge": hedge,
        "formation_days": config.formation_days,
        "trading_days": config.trading_days,
        "entry_z": config.signal.entry_z,
        "exit_z": config.signal.exit_z,
        "stop_z": config.signal.stop_z,
        "time_stop_days": config.signal.time_stop_bars,
        "capital": config.capital,
        "gross_exposure": config.gross_exposure,
        "neutrality": config.neutrality if kind == "pair" else "eigenvector",
        "cost_bps_per_leg": costs.cost_bps_per_leg,
        "borrow_fee_bps_annual": costs.borrow_fee_bps_annual,
        "borrow_day_count": costs.borrow_day_count,
        "kalman_memory_days": config.kalman_memory_days if hedge == "kalman" else None,
        "basket_det_order": config.basket_det_order if kind == "basket" else None,
        "basket_k_ar_diff": config.basket_k_ar_diff if kind == "basket" else None,
    }
    return BacktestResult(
        kind=kind,
        labels=labels,
        hedge=hedge,
        cost_bps=costs.cost_bps_per_leg,
        daily=daily,
        trades=ledger.trades,
        signals=signals,
        windows=windows,
        first_signal_date=index[config.formation_days],
        settings=settings,
    )


def run_pair_backtest(
    a: pd.DataFrame,
    b: pd.DataFrame,
    *,
    asof: pd.Timestamp | str,
    config: BacktestConfig,
    hedge: str | None = None,
    cost_bps: float | None = None,
    labels: tuple[str, str] = ("A", "B"),
) -> BacktestResult:
    """Walk-forward backtest of one pair on the rows strictly before `asof`.

    Args:
        a, b: Price frames with the columns close, dividends, capital_gains
            and tr_close (the output of the price source's load), on identical
            dates before `asof`.
        asof: As-of date. No row dated on or after it is read.
        config: Backtest settings.
        hedge: Hedge variant; default config.hedge_default.
        cost_bps: Trading cost per leg; default config.cost_bps_per_leg.
        labels: Names of the two legs.

    Raises:
        ValueError: If the legs' dates differ, there are fewer than
            formation_days + 2 rows, a price is not positive, or for any reason
            rows_before raises.
    """
    if labels[0] == labels[1]:
        raise ValueError("the two legs need different labels")
    hedge = hedge or config.hedge_default
    cut = _prepare({labels[0]: a, labels[1]: b}, asof, config)
    log_a = np.log(cut[labels[0]]["tr_close"])
    log_b = np.log(cut[labels[1]]["tr_close"])
    signals, windows = pair_signal_frame(
        log_a, log_b, hedge=hedge, formation=config.formation_days,
        trading=config.trading_days, neutrality=config.neutrality,
        kalman_discount=config.kalman_discount,
    )
    signals = signals.rename(
        columns={"weight_a": f"weight_{labels[0]}", "weight_b": f"weight_{labels[1]}"}
    )
    weight_columns = [f"weight_{labels[0]}", f"weight_{labels[1]}"]
    return _finish("pair", hedge, cut, signals, windows, weight_columns, config, cost_bps)


def run_basket_backtest(
    frames: dict[str, pd.DataFrame],
    *,
    asof: pd.Timestamp | str,
    config: BacktestConfig,
    cost_bps: float | None = None,
) -> BacktestResult:
    """Walk-forward backtest of a Johansen basket on the rows before `asof`.

    Args:
        frames: Price frame per asset (same columns as for a pair), at least
            three assets, on identical dates before `asof`.
        asof, config, cost_bps: As for run_pair_backtest.
    """
    if len(frames) < 3:
        raise ValueError("a basket needs at least three assets")
    cut = _prepare(dict(frames), asof, config)
    log_prices = pd.DataFrame({label: np.log(f["tr_close"]) for label, f in cut.items()})
    signals, windows = basket_signal_frame(
        log_prices, formation=config.formation_days, trading=config.trading_days,
        det_order=config.basket_det_order, k_ar_diff=config.basket_k_ar_diff,
    )
    weight_columns = [f"weight_{label}" for label in cut]
    return _finish(
        "basket", "johansen", cut, signals, windows, weight_columns, config, cost_bps
    )

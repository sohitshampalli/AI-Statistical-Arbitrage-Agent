"""Tests for the walk-forward engine on simulated data.

The engine's look-ahead protection is tested as prefix invariance: a backtest
on the first k rows must equal the first k rows of a backtest on all rows, for
every output (signals, ledger, closed trades). If any value on a row used a
later row, cutting the data there would change it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from statarb_agent.backtest.engine import (
    basket_signal_frame,
    pair_signal_frame,
    run_basket_backtest,
    run_pair_backtest,
    window_layout,
)
from statarb_agent.data.synthetic import (
    as_price_frame,
    simulate_basket,
    simulate_cointegrated_pair,
)
from statarb_agent.stats.hedge_ratio import ols_hedge_ratio, ols_residual_sd
from statarb_agent.stats.johansen import johansen_test

ASOF = "2100-01-01"
N = 900
HEDGES = ("static", "rolling", "kalman")


@pytest.fixture(scope="module")
def pair() -> pd.DataFrame:
    return simulate_cointegrated_pair(seed=21, n_obs=N)


@pytest.fixture(scope="module")
def legs(pair: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    return as_price_frame(pair["log_a"]), as_price_frame(pair["log_b"])


def test_window_layout_by_hand() -> None:
    window, last = window_layout(12, formation=4, trading=3)
    assert list(window) == [-1, -1, -1, -1, 0, 0, 0, 1, 1, 1, 2, 2]
    assert list(np.flatnonzero(last)) == [6, 9]  # window 2 is not complete
    window, last = window_layout(3, formation=4, trading=3)
    assert list(window) == [-1, -1, -1] and not last.any()


def test_static_parameters_come_from_the_formation_rows(pair: pd.DataFrame) -> None:
    signals, windows = pair_signal_frame(
        pair["log_a"], pair["log_b"], hedge="static", formation=252, trading=63,
        neutrality="dollar", kalman_discount=0.99,
    )
    assert signals["window"].max() == (N - 252 - 1) // 63 and len(windows) == 11
    assert signals.iloc[:252][["alpha", "beta", "sigma", "z"]].isna().all().all()
    assert not signals["tradeable"].iloc[:252].any()
    for k in (0, 3, 10):
        t0 = 252 + 63 * k
        rows_a, rows_b = pair["log_a"].iloc[t0 - 252 : t0], pair["log_b"].iloc[t0 - 252 : t0]
        fit = ols_hedge_ratio(rows_a, rows_b, pair.index[t0])
        sd = ols_residual_sd(rows_a, rows_b, fit)
        block = signals.iloc[t0 : min(t0 + 63, N)]
        assert (block["alpha"] == fit.alpha).all() and (block["beta"] == fit.beta).all()
        assert (block["sigma"] == sd).all()
        row = windows.iloc[k]
        assert row["formation_start"] == pair.index[t0 - 252]
        assert row["formation_end"] == pair.index[t0 - 1]
        assert row["trade_start"] == pair.index[t0] and row["beta"] == fit.beta
        t = t0 + 5
        expected = (pair["log_a"].iloc[t] - fit.alpha - fit.beta * pair["log_b"].iloc[t]) / sd
        assert signals["z"].iloc[t] == pytest.approx(expected, rel=1e-12)
    assert (signals.loc[signals["tradeable"], ["weight_a", "weight_b"]] == [0.5, -0.5]).all().all()


def test_rolling_parameters_use_the_rows_just_before_each_bar(pair: pd.DataFrame) -> None:
    signals, _ = pair_signal_frame(
        pair["log_a"], pair["log_b"], hedge="rolling", formation=252, trading=63,
        neutrality="dollar", kalman_discount=0.99,
    )
    for t in (252, 300, 899):
        rows_a, rows_b = pair["log_a"].iloc[t - 252 : t], pair["log_b"].iloc[t - 252 : t]
        fit = ols_hedge_ratio(rows_a, rows_b, pair.index[t])
        sd = ols_residual_sd(rows_a, rows_b, fit)
        assert signals["beta"].iloc[t] == pytest.approx(fit.beta, rel=1e-9)
        expected = (pair["log_a"].iloc[t] - fit.alpha - fit.beta * pair["log_b"].iloc[t]) / sd
        assert signals["z"].iloc[t] == pytest.approx(expected, rel=1e-7)


def test_kalman_first_bar_by_hand(pair: pd.DataFrame) -> None:
    """On a window's first bar the forecast is the formation OLS fit, and the
    forecast variance is H (P0 / lam) H' + R with P0 the OLS covariance."""
    lam = 1.0 - 1.0 / 252
    signals, _ = pair_signal_frame(
        pair["log_a"], pair["log_b"], hedge="kalman", formation=252, trading=63,
        neutrality="dollar", kalman_discount=lam,
    )
    for t0 in (252, 252 + 63 * 4):
        rows_a, rows_b = pair["log_a"].iloc[t0 - 252 : t0], pair["log_b"].iloc[t0 - 252 : t0]
        fit = ols_hedge_ratio(rows_a, rows_b, pair.index[t0])
        sd = ols_residual_sd(rows_a, rows_b, fit)
        design = np.column_stack([np.ones(252), rows_b.to_numpy()])
        p0 = sd**2 * np.linalg.inv(design.T @ design)
        h = np.array([1.0, pair["log_b"].iloc[t0]])
        q = h @ (p0 / lam) @ h + sd**2
        row = signals.iloc[t0]
        assert row["alpha"] == pytest.approx(fit.alpha, rel=1e-12)
        assert row["beta"] == pytest.approx(fit.beta, rel=1e-12)
        assert row["sigma"] == pytest.approx(np.sqrt(q), rel=1e-9)
        innovation = pair["log_a"].iloc[t0] - fit.alpha - fit.beta * pair["log_b"].iloc[t0]
        assert row["z"] == pytest.approx(innovation / np.sqrt(q), rel=1e-9)
    # later bars in the window move away from the formation fit
    assert signals["beta"].iloc[253] != signals["beta"].iloc[252]


@pytest.mark.parametrize("hedge", HEDGES)
def test_positions_follow_decisions_by_exactly_one_bar(
    legs: tuple[pd.DataFrame, pd.DataFrame], bt_config, hedge: str
) -> None:
    result = run_pair_backtest(*legs, asof=ASOF, config=bt_config(), hedge=hedge)
    decision = result.signals["decision"].to_numpy()
    position = result.daily["position"].to_numpy()
    assert position[0] == 0
    np.testing.assert_array_equal(position[1:], decision[:-1])
    assert (position[:253] == 0).all()  # first signal on row 252, first fill on 253
    assert result.first_signal_date == legs[0].index[252]
    assert len(result.trades) > 0 and result.hedge == hedge
    # every exit on a window's last signal bar is filled on the next bar
    ends = result.trades.loc[result.trades["exit_reason"] == "window_end"]
    last_bars = set(result.signals.index[result.signals["window_last"]])
    assert set(ends["exit_signal_date"]) <= last_bars
    # no position is held over from one window's parameters to the next:
    # the bar after a window's last signal bar is flat
    after_last = np.flatnonzero(result.signals["window_last"].to_numpy()) + 1
    assert (position[after_last[after_last < len(position)]] == 0).all()


@pytest.mark.parametrize("hedge", HEDGES)
def test_prefix_invariance(
    legs: tuple[pd.DataFrame, pd.DataFrame], bt_config, hedge: str
) -> None:
    """Look-ahead test: cutting the data at row k leaves rows before k unchanged."""
    a, b = legs
    config = bt_config()
    full = run_pair_backtest(a, b, asof=ASOF, config=config, hedge=hedge)
    for k in (254, 315, 316, 400, 641, 899):
        part = run_pair_backtest(a, b, asof=a.index[k], config=config, hedge=hedge)
        assert len(part.daily) == k
        pd.testing.assert_frame_equal(part.daily, full.daily.iloc[:k], check_exact=True)
        pd.testing.assert_frame_equal(part.signals, full.signals.iloc[:k], check_exact=True)
        closed = part.trades.loc[~part.trades["open"]].reset_index(drop=True)
        expected = full.trades.loc[full.trades["exit_date"] < a.index[k]]
        pd.testing.assert_frame_equal(
            closed, expected.reset_index(drop=True), check_exact=True
        )


@pytest.mark.parametrize("hedge", HEDGES)
def test_rows_at_or_after_asof_are_never_read(
    legs: tuple[pd.DataFrame, pd.DataFrame], bt_config, hedge: str
) -> None:
    """Look-ahead test: prices, payouts, NaN and infinity from asof on change nothing."""
    a, b = legs
    asof = a.index[700]
    config = bt_config()
    before = run_pair_backtest(a, b, asof=asof, config=config, hedge=hedge)
    a2, b2 = a.copy(), b.copy()
    rng = np.random.default_rng(5)
    a2.iloc[700:, :] = rng.uniform(1.0, 500.0, (N - 700, 4))  # includes the asof row
    b2.iloc[700:, 0] = np.nan
    b2.iloc[750, 3] = np.inf
    b2.iloc[705, 1] = 99.0
    after = run_pair_backtest(a2, b2, asof=asof, config=config, hedge=hedge)
    pd.testing.assert_frame_equal(after.daily, before.daily, check_exact=True)
    pd.testing.assert_frame_equal(after.signals, before.signals, check_exact=True)
    pd.testing.assert_frame_equal(after.trades, before.trades, check_exact=True)
    assert before.daily.index.max() == a.index[699]


def test_cost_levels_change_costs_only(
    legs: tuple[pd.DataFrame, pd.DataFrame], bt_config
) -> None:
    config = bt_config()
    free = run_pair_backtest(*legs, asof=ASOF, config=config, cost_bps=0.0)
    base = run_pair_backtest(*legs, asof=ASOF, config=config)
    double = run_pair_backtest(*legs, asof=ASOF, config=config, cost_bps=20.0)
    assert (free.cost_bps, base.cost_bps, double.cost_bps) == (0.0, 10.0, 20.0)
    for other in (base, double):
        np.testing.assert_array_equal(other.daily["position"], free.daily["position"])
        np.testing.assert_allclose(other.daily["gross_pnl"], free.daily["gross_pnl"])
        np.testing.assert_allclose(other.daily["borrow_cost"], free.daily["borrow_cost"])
    assert (free.daily["trade_cost"] == 0.0).all()
    np.testing.assert_allclose(double.daily["trade_cost"], 2.0 * base.daily["trade_cost"])
    assert free.daily["pnl"].sum() > base.daily["pnl"].sum() > double.daily["pnl"].sum()
    assert base.settings["cost_bps_per_leg"] == 10.0
    assert base.settings["time_stop_days"] == 30 and base.settings["hedge"] == "static"


def test_beta_neutral_weights(legs: tuple[pd.DataFrame, pd.DataFrame], bt_config) -> None:
    result = run_pair_backtest(*legs, asof=ASOF, config=bt_config(neutrality="beta"))
    s = result.signals.loc[result.signals["tradeable"]]
    np.testing.assert_allclose(s["weight_A"] + s["weight_B"].abs(), 1.0)
    np.testing.assert_allclose(-s["weight_B"] / s["weight_A"], s["beta"])
    trade = result.trades.iloc[0]
    beta = result.signals.loc[trade["entry_signal_date"], "beta"]
    assert -trade["notional_B"] / trade["notional_A"] == pytest.approx(beta)
    assert abs(trade["notional_A"]) + abs(trade["notional_B"]) == pytest.approx(1e6)
    dollar = run_pair_backtest(*legs, asof=ASOF, config=bt_config()).trades.iloc[0]
    assert abs(dollar["notional_A"]) == pytest.approx(5e5)
    assert dollar["notional_A"] == pytest.approx(-dollar["notional_B"])
    assert np.sign(dollar["notional_A"]) == dollar["side"]


def test_negative_beta_is_not_traded(pair: pd.DataFrame, bt_config) -> None:
    """A pair that moves in opposite directions has beta < 0 and is left alone."""
    mirrored = 2.0 * pair["log_b"].iloc[0] - pair["log_b"]  # log_b reflected
    a = as_price_frame(pair["log_a"])
    b = as_price_frame(mirrored)
    for hedge in HEDGES:
        result = run_pair_backtest(a, b, asof=ASOF, config=bt_config(), hedge=hedge)
        assert (result.signals["beta"].dropna() < 0).all()
        assert not result.signals["tradeable"].any()
        assert len(result.trades) == 0 and (result.daily["pnl"] == 0.0).all()


def test_distributions_reach_the_ledger(pair: pd.DataFrame, bt_config) -> None:
    """A dividend on leg A is received when long A and owed when short A.

    The signal uses tr_close, which is unchanged here, so the trades are the
    same as without the dividend; only the split between price and
    distribution profit moves.
    """
    a = as_price_frame(pair["log_a"])
    b = as_price_frame(pair["log_b"])
    plain = run_pair_backtest(a, b, asof=ASOF, config=bt_config())
    paying = a.copy()
    held_long = plain.daily.index[(plain.daily["shares_A"] > 0).to_numpy()]
    held_short = plain.daily.index[(plain.daily["shares_A"] < 0).to_numpy()]
    day_long, day_short = held_long[3], held_short[3]
    for day in (day_long, day_short):
        row = paying.index.get_loc(day)
        paying.iloc[row, paying.columns.get_loc("dividends")] = 1.0
        # the price drops by the dividend on the ex-date; total return is unchanged
        paying.iloc[row:, paying.columns.get_loc("close")] -= 1.0
    result = run_pair_backtest(paying, b, asof=ASOF, config=bt_config())
    np.testing.assert_array_equal(result.daily["position"], plain.daily["position"])
    shares_long = plain.daily["shares_A"].shift(1).loc[day_long]
    assert shares_long > 0
    assert result.daily.loc[day_long, "dist_pnl"] == pytest.approx(
        result.daily["shares_A"].shift(1).loc[day_long] * 1.0
    )
    assert result.daily.loc[day_long, "dist_pnl"] > 0
    assert result.daily.loc[day_short, "dist_pnl"] < 0


def test_errors(legs: tuple[pd.DataFrame, pd.DataFrame], bt_config) -> None:
    a, b = legs
    config = bt_config()
    with pytest.raises(ValueError, match="different dates"):
        run_pair_backtest(a, b.drop(b.index[10]), asof=ASOF, config=config)
    with pytest.raises(ValueError, match="at least 254 rows"):
        run_pair_backtest(a, b, asof=a.index[253], config=config)
    with pytest.raises(ValueError, match="missing the columns"):
        run_pair_backtest(a.drop(columns="dividends"), b, asof=ASOF, config=config)
    with pytest.raises(ValueError, match="different labels"):
        run_pair_backtest(a, b, asof=ASOF, config=config, labels=("X", "X"))
    with pytest.raises(ValueError, match="hedge must be"):
        run_pair_backtest(a, b, asof=ASOF, config=config, hedge="magic")
    with pytest.raises(ValueError, match="three assets"):
        run_basket_backtest({"A": a, "B": b}, asof=ASOF, config=config)
    bad = a.copy()
    bad.iloc[5, 0] = -1.0
    with pytest.raises(ValueError, match="non-positive"):
        run_pair_backtest(bad, b, asof=ASOF, config=config)


# Basket ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def basket() -> dict[str, pd.DataFrame]:
    frame = simulate_basket(seed=31, n_obs=N)
    return {name: as_price_frame(frame[name]) for name in frame.columns}


def test_basket_weights_come_from_the_formation_rows(basket) -> None:
    logs = pd.DataFrame({k: np.log(v["tr_close"]) for k, v in basket.items()})
    signals, windows = basket_signal_frame(
        logs, formation=252, trading=63, det_order=0, k_ar_diff=1
    )
    for k in (0, 5):
        t0 = 252 + 63 * k
        res = johansen_test(logs.iloc[t0 - 252 : t0], logs.index[t0])
        w = np.array(res.weights)
        block = signals.iloc[t0 : t0 + 63]
        np.testing.assert_array_equal(
            block[["weight_x1", "weight_x2", "weight_x3"]].to_numpy(), np.tile(w, (63, 1))
        )
        combo = logs.iloc[t0 - 252 : t0].to_numpy() @ w
        t = t0 + 7
        expected = (logs.iloc[t].to_numpy() @ w - combo.mean()) / combo.std(ddof=1)
        assert signals["z"].iloc[t] == pytest.approx(expected, rel=1e-9)
        assert windows.iloc[k]["rank_trace"] == res.rank_trace
        assert (block["rank"] == res.rank_trace).all()
    assert signals["z"].iloc[:252].isna().all()


def test_basket_prefix_invariance_and_lag(basket, bt_config) -> None:
    config = bt_config()
    full = run_basket_backtest(basket, asof=ASOF, config=config)
    assert full.kind == "basket" and full.hedge == "johansen"
    assert full.labels == ("x1", "x2", "x3") and len(full.trades) > 0
    np.testing.assert_array_equal(
        full.daily["position"].to_numpy()[1:], full.signals["decision"].to_numpy()[:-1]
    )
    index = basket["x1"].index
    for k in (300, 316, 700):
        part = run_basket_backtest(basket, asof=index[k], config=config)
        pd.testing.assert_frame_equal(part.daily, full.daily.iloc[:k], check_exact=True)
        pd.testing.assert_frame_equal(part.signals, full.signals.iloc[:k], check_exact=True)
    trade = full.trades.iloc[0]
    notional = trade[["notional_x1", "notional_x2", "notional_x3"]].to_numpy(dtype=float)
    assert np.abs(notional).sum() == pytest.approx(1e6)
    weights = full.signals.loc[
        trade["entry_signal_date"], ["weight_x1", "weight_x2", "weight_x3"]
    ].to_numpy(dtype=float)
    np.testing.assert_allclose(notional, trade["side"] * weights * 1e6)

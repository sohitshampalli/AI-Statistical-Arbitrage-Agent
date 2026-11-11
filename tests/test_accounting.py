"""Tests for the ledger. The main case is booked by hand in the docstring."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from statarb_agent.backtest.accounting import CostModel, simulate_ledger

LABELS = ("A", "B")
COSTS = CostModel(cost_bps_per_leg=10.0, borrow_fee_bps_annual=360.0)  # 1 bp a day
INDEX = pd.date_range("2020-01-01", periods=6, freq="D", name="date")
CLOSE = np.array(
    [[10.0, 20.0], [10.0, 20.0], [11.0, 20.0], [12.0, 21.0], [12.0, 22.0], [12.0, 22.0]]
)
DIST = np.zeros((6, 2))
DIST[2, 0] = 0.2  # A goes ex-dividend on bar 2
DIST[3, 1] = 0.4  # B goes ex-dividend on bar 3
TARGET = np.array([1, 1, 0, -1, -1, -1])
WEIGHTS = np.tile([0.5, -0.5], (6, 1))


def run(**changes: object):
    kwargs = {
        "index": INDEX, "close": CLOSE, "distributions": DIST, "target": TARGET,
        "dollar_weights": WEIGHTS, "labels": LABELS, "capital": 1000.0,
        "gross_exposure": 1.0, "costs": COSTS,
        "reasons": np.array(["entry_long", "", "exit", "entry_short", "", ""], object),
        "z": np.array([-2.5, -1.0, -0.2, 2.5, 2.0, 1.5]),
    }
    kwargs.update(changes)
    index = kwargs.pop("index")
    close = kwargs.pop("close")
    dist = kwargs.pop("distributions")
    target = kwargs.pop("target")
    weights = kwargs.pop("dollar_weights")
    return simulate_ledger(index, close, dist, target, weights, **kwargs)


def test_hand_booked_example() -> None:
    """Capital 1000, 10 bps per leg, borrow 360 bps a year (1 bp per day).

    Bar 0: decide long the spread. Nothing happens yet.
    Bar 1: execute. Buy 500 of A at 10 (50 shares), short 500 of B at 20 (-25
           shares). Cost 1000 * 0.001 = 1. pnl -1, equity 999.
    Bar 2: A 10 -> 11: +50. A pays 0.2 a share: +10. Borrow on 500 short for one
           day: 0.05. pnl 59.95, equity 1058.95. Decision: flat.
    Bar 3: A 11 -> 12: +50. B 20 -> 21: -25. B pays 0.4 a share, owed on the
           short: -10. Borrow 0.05. Exit trades 600 + 525 = 1125: cost 1.125.
           pnl 13.825, equity 1072.775. Decision: short the spread.
    Bar 4: execute. Short 500 of A at 12, buy 500 of B at 22. Cost 1. Price
           move 0 (flat until this close). pnl -1, equity 1071.775.
    Bar 5: no price change. Borrow 0.05 on the A short. pnl -0.05.
    """
    ledger = run()
    d = ledger.daily
    np.testing.assert_allclose(d["pnl"], [0, -1, 59.95, 13.825, -1, -0.05], atol=1e-12)
    np.testing.assert_allclose(
        d["equity"], [1000, 999, 1058.95, 1072.775, 1071.775, 1071.725], atol=1e-9
    )
    np.testing.assert_allclose(d["price_pnl"], [0, 0, 50, 25, 0, 0], atol=1e-12)
    np.testing.assert_allclose(d["dist_pnl"], [0, 0, 10, -10, 0, 0], atol=1e-12)
    np.testing.assert_allclose(d["borrow_cost"], [0, 0, 0.05, 0.05, 0, 0.05], atol=1e-12)
    np.testing.assert_allclose(d["trade_cost"], [0, 1, 0, 1.125, 1, 0], atol=1e-12)
    np.testing.assert_allclose(d["traded_notional"], [0, 1000, 0, 1125, 1000, 0])
    assert list(d["position"]) == [0, 1, 1, 0, -1, -1]
    assert list(d["decision"]) == list(TARGET)
    np.testing.assert_allclose(d["shares_A"], [0, 50, 50, 0, -500 / 12, -500 / 12])
    np.testing.assert_allclose(d["shares_B"], [0, -25, -25, 0, 500 / 22, 500 / 22])
    np.testing.assert_allclose(d["gross_exposure"], [0, 1000, 1050, 0, 1000, 1000])
    np.testing.assert_allclose(d["net_exposure"], [0, 0, 50, 0, 0, 0], atol=1e-9)
    np.testing.assert_allclose(d["ret"], d["pnl"] / 1000.0)
    np.testing.assert_allclose(d["gross_pnl"], [0, 0, 60, 15, 0, 0], atol=1e-12)
    np.testing.assert_allclose(d["gross_ret"], d["gross_pnl"] / 1000.0)

    t = ledger.trades
    assert len(t) == 2
    first, second = t.iloc[0], t.iloc[1]
    assert (first["side"], first["bars_held"], bool(first["open"])) == (1, 2, False)
    assert first["entry_signal_date"] == INDEX[0] and first["entry_date"] == INDEX[1]
    assert first["exit_signal_date"] == INDEX[2] and first["exit_date"] == INDEX[3]
    assert first["exit_reason"] == "exit"
    assert (first["entry_z"], first["exit_z"]) == (-2.5, -0.2)
    assert first["price_pnl"] == pytest.approx(75.0)
    assert first["dist_pnl"] == pytest.approx(0.0)
    assert first["borrow_cost"] == pytest.approx(0.10)
    assert first["trade_cost"] == pytest.approx(2.125)
    assert first["net_pnl"] == pytest.approx(72.775)
    assert first["notional_A"] == pytest.approx(500.0)
    assert first["notional_B"] == pytest.approx(-500.0)
    assert (second["side"], bool(second["open"]), second["bars_held"]) == (-1, True, 1)
    assert pd.isna(second["exit_date"]) and second["exit_reason"] == ""
    assert second["net_pnl"] == pytest.approx(-1.05)
    assert second["notional_A"] == pytest.approx(-500.0)


def test_equity_identity_and_trade_sum() -> None:
    """equity = cash + shares * close; pnl is the change in equity; the trades'
    net profits add up to the total."""
    rng = np.random.default_rng(0)
    n = 300
    index = pd.bdate_range("2015-01-01", periods=n, name="date")
    close = 50.0 * np.exp(np.cumsum(0.02 * rng.standard_normal((n, 2)), axis=0))
    dist = np.where(rng.random((n, 2)) < 0.02, 0.3, 0.0)
    target = np.repeat(rng.choice([-1, 0, 1], size=n // 10), 10)
    weights = np.tile([0.6, -0.4], (n, 1))
    ledger = simulate_ledger(
        index, close, dist, target, weights, labels=LABELS, capital=1e6,
        gross_exposure=1.0, costs=CostModel(10.0, 50.0),
    )
    d = ledger.daily
    value = d["shares_A"] * close[:, 0] + d["shares_B"] * close[:, 1]
    np.testing.assert_allclose(d["equity"], d["cash"] + value, rtol=1e-12)
    np.testing.assert_allclose(np.diff(d["equity"]), d["pnl"].iloc[1:], atol=1e-6)
    assert d["equity"].iloc[0] == 1e6 and d["pnl"].iloc[0] == 0.0
    assert ledger.trades["net_pnl"].sum() == pytest.approx(d["pnl"].sum(), abs=1e-6)
    for part in ("price_pnl", "dist_pnl", "borrow_cost", "trade_cost"):
        assert ledger.trades[part].sum() == pytest.approx(d[part].sum(), abs=1e-6)
    assert len(ledger.trades) > 5 and (ledger.trades["side"] != 0).all()


def test_costs_scale_as_documented() -> None:
    free = run(costs=CostModel(0.0, 0.0)).daily
    np.testing.assert_allclose(free["pnl"], free["gross_pnl"])
    np.testing.assert_allclose(free["pnl"], [0, 0, 60, 15, 0, 0], atol=1e-12)
    double = run(costs=CostModel(20.0, 720.0)).daily
    base = run().daily
    np.testing.assert_allclose(double["trade_cost"], 2 * base["trade_cost"])
    np.testing.assert_allclose(double["borrow_cost"], 2 * base["borrow_cost"])
    np.testing.assert_allclose(double["gross_pnl"], base["gross_pnl"])
    year365 = run(costs=CostModel(10.0, 365.0, borrow_day_count=365)).daily
    assert year365["borrow_cost"].iloc[2] == pytest.approx(500 * 0.0001)


def test_borrow_fee_uses_calendar_days() -> None:
    index = pd.DatetimeIndex(
        ["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"], name="date"
    )  # Thursday, Friday, Monday, Tuesday
    close = np.full((4, 2), 10.0)
    ledger = simulate_ledger(
        index, close, np.zeros((4, 2)), np.array([1, 1, 1, 1]),
        np.tile([0.5, -0.5], (4, 1)), labels=LABELS, capital=1000.0,
        gross_exposure=1.0, costs=CostModel(0.0, 360.0),
    )
    # entered at Friday's close; the weekend is three calendar days
    np.testing.assert_allclose(ledger.daily["borrow_cost"], [0, 0, 0.15, 0.05])


def test_sizing_uses_initial_capital_and_gross_exposure() -> None:
    half = run(gross_exposure=0.5).daily
    np.testing.assert_allclose(half["shares_A"].iloc[1], 25.0)
    np.testing.assert_allclose(half["gross_exposure"].iloc[1], 500.0)
    # the second entry is sized on 1000 although equity is then about 1072
    np.testing.assert_allclose(run().daily["gross_exposure"].iloc[4], 1000.0)


def test_last_decision_is_never_executed_and_rows_do_not_see_the_future() -> None:
    """Look-ahead test: row t depends on prices up to t and decisions up to t - 1."""
    full = run()
    for cut in range(1, 7):
        part = simulate_ledger(
            INDEX[:cut], CLOSE[:cut], DIST[:cut], TARGET[:cut], WEIGHTS[:cut],
            labels=LABELS, capital=1000.0, gross_exposure=1.0, costs=COSTS,
        )
        pd.testing.assert_frame_equal(
            part.daily, full.daily.iloc[:cut], check_exact=True
        )
    one = run(target=np.array([1, 0, 0, 0, 0, 0]))  # decided on bar 0, undone on bar 1
    assert list(one.daily["position"]) == [0, 1, 0, 0, 0, 0]
    last = run(target=np.array([0, 0, 0, 0, 0, 1]))
    assert (last.daily["position"] == 0).all() and len(last.trades) == 0
    # changing a later price or decision leaves earlier rows alone
    close = CLOSE.copy()
    close[4:] *= 3.0
    target = TARGET.copy()
    target[3:] = 0
    changed = run(close=close, target=target)
    # Row 3 echoes its own decision, which was changed; everything booked on
    # row 3 comes from decisions up to bar 2 and is unchanged.
    booked = [c for c in full.daily.columns if c != "decision"]
    pd.testing.assert_frame_equal(
        changed.daily.iloc[:4][booked], full.daily.iloc[:4][booked], check_exact=True
    )
    assert list(changed.daily["decision"].iloc[:3]) == list(full.daily["decision"].iloc[:3])
    assert changed.daily["position"].iloc[4] == 0 and full.daily["position"].iloc[4] == -1


def test_direct_reversal_pays_both_ways() -> None:
    ledger = run(target=np.array([1, -1, -1, 0, 0, 0]), distributions=np.zeros((6, 2)))
    d = ledger.daily
    assert list(d["position"]) == [0, 1, -1, -1, 0, 0]
    # bar 2: close 50 A at 11 and -25 B at 20 (550 + 500), open 500 + 500
    assert d["traded_notional"].iloc[2] == pytest.approx(2050.0)
    assert len(ledger.trades) == 2
    assert ledger.trades["trade_cost"].iloc[0] == pytest.approx(1.0 + 1.05)
    assert ledger.trades["trade_cost"].iloc[1] == pytest.approx(1.0 + d["trade_cost"].iloc[4])
    assert ledger.trades["net_pnl"].sum() == pytest.approx(d["pnl"].sum())


def test_three_assets() -> None:
    index = pd.date_range("2020-01-01", periods=3, freq="D", name="date")
    close = np.array([[10.0, 20.0, 40.0], [10.0, 20.0, 40.0], [11.0, 20.0, 38.0]])
    weights = np.tile([0.5, -0.3, -0.2], (3, 1))
    ledger = simulate_ledger(
        index, close, np.zeros((3, 3)), np.array([-1, -1, -1]), weights,
        labels=("X", "Y", "Z"), capital=1000.0, gross_exposure=1.0,
        costs=CostModel(0.0, 0.0),
    )
    d = ledger.daily
    # short the spread: -500 of X (-50 shares), +300 of Y (15), +200 of Z (5)
    assert list(d[["shares_X", "shares_Y", "shares_Z"]].iloc[1]) == [-50.0, 15.0, 5.0]
    assert d["pnl"].iloc[2] == pytest.approx(-50.0 * 1.0 + 5.0 * -2.0)
    assert list(ledger.trades.columns[-3:]) == ["notional_X", "notional_Y", "notional_Z"]


def test_no_trades_gives_an_empty_typed_trade_list() -> None:
    ledger = run(target=np.zeros(6, dtype=int))
    assert len(ledger.trades) == 0 and "net_pnl" in ledger.trades.columns
    # same column dtypes as a ledger with trades
    pd.testing.assert_series_equal(ledger.trades.dtypes, run().trades.dtypes)
    assert (ledger.daily["equity"] == 1000.0).all()


@pytest.mark.parametrize(
    "changes",
    [
        {"close": CLOSE[:5]},
        {"close": np.where(CLOSE == 11.0, -1.0, CLOSE)},
        {"close": np.where(CLOSE == 11.0, np.nan, CLOSE)},
        {"distributions": -np.ones((6, 2))},
        {"target": np.array([2, 0, 0, 0, 0, 0])},
        {"dollar_weights": np.tile([0.7, -0.5], (6, 1))},
        {"dollar_weights": np.tile([np.nan, -0.5], (6, 1))},
        {"capital": 0.0},
        {"gross_exposure": -1.0},
        {"index": INDEX[::-1]},
        {"z": np.zeros(3)},
    ],
)
def test_invalid_inputs_raise(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        run(**changes)


def test_cost_model_validation() -> None:
    with pytest.raises(ValueError):
        CostModel(-1.0, 0.0)
    with pytest.raises(ValueError):
        CostModel(1.0, float("nan"))
    with pytest.raises(ValueError):
        CostModel(1.0, 1.0, borrow_day_count=252)

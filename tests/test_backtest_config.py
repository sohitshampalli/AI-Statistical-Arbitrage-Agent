"""Tests for the backtest config loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from statarb_agent.backtest.config import load_backtest_config

REPO_ROOT = Path(__file__).resolve().parents[1]
PATH = REPO_ROOT / "configs" / "backtest.yaml"


def test_project_config_loads_with_the_documented_values() -> None:
    c = load_backtest_config(PATH)
    assert (c.formation_days, c.trading_days) == (252, 63)
    s = c.signal
    assert (s.entry_z, s.exit_z, s.stop_z, s.time_stop_bars) == (2.0, 0.5, 4.0, 30)
    assert c.hedge_default == "static"
    assert c.hedge_variants == ("static", "rolling", "kalman")
    assert c.kalman_memory_days == 252
    assert c.kalman_discount == pytest.approx(1 - 1 / 252)
    assert (c.capital, c.gross_exposure, c.neutrality) == (1_000_000.0, 1.0, "dollar")
    assert c.cost_bps_per_leg == 10.0 and c.cost_sensitivity_bps == (0.0, 10.0, 20.0)
    assert (c.borrow_fee_bps_annual, c.borrow_day_count) == (50.0, 360)
    assert (c.basket_det_order, c.basket_k_ar_diff) == (0, 1)
    k = c.controls
    assert (k.synthetic_seed, k.random_walk_seed) == (20261111, 20261112)
    assert (k.n_obs, k.half_life, k.beta, k.alpha) == (3130, 10.0, 1.5, 0.3)
    assert (k.spread_sd, k.sigma) == (0.02, 0.015)
    assert (k.batch_first_seed, k.batch_size) == (30000, 200)
    assert (k.placebo_first_seed, k.placebo_shuffles) == (40000, 200)
    costs = c.cost_model()
    assert (costs.cost_bps_per_leg, costs.borrow_fee_bps_annual) == (10.0, 50.0)
    assert c.cost_model(20.0).cost_bps_per_leg == 20.0


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("formation_days: 252", "formation_days: 10"),
        ("formation_days: 252", "formation_days: 252.5"),
        ("entry_z: 2.0", "entry_z: 0.4"),
        ("stop_z: 4.0", "stop_z: 1.0"),
        ("time_stop_days: 30", "time_stop_days: 0"),
        ("default: static", "default: magic"),
        ("variants: [static, rolling, kalman]", "variants: [static, static]"),
        ("variants: [static, rolling, kalman]", "variants: []"),
        ("variants: [static, rolling, kalman]", "variants: static"),
        ("kalman_memory_days: 252", "kalman_memory_days: 1"),
        ("capital: 1000000", "capital: 0"),
        ("gross_exposure: 1.0", "gross_exposure: -1"),
        ("neutrality: dollar", "neutrality: none"),
        ("cost_bps_per_leg: 10", "cost_bps_per_leg: -1"),
        ("sensitivity_bps: [0, 10, 20]", "sensitivity_bps: [0, -5]"),
        ("sensitivity_bps: [0, 10, 20]", "sensitivity_bps: 10"),
        ("borrow_day_count: 360", "borrow_day_count: 252"),
        ("borrow_fee_bps_annual: 50", "borrow_fee_bps_annual: fifty"),
        ("batch_size: 200", "batch_size: 1"),
        ("  k_ar_diff: 1", "  k_ar_diff: 1\n  extra: 2"),
        ("walk_forward:", "walk_forwards:"),
    ],
)
def test_bad_configs_raise(tmp_path: Path, old: str, new: str) -> None:
    text = PATH.read_text()
    assert text.count(old) == 1
    path = tmp_path / "backtest.yaml"
    path.write_text(text.replace(old, new))
    with pytest.raises((ValueError, TypeError)):
        load_backtest_config(path)

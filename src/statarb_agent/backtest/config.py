"""Backtest settings: the validated contents of configs/backtest.yaml.

The YAML file explains where each value comes from. Nothing here may be changed
after a real-data backtest has been seen; a run with different values is a new
trial and is logged as one (every run records the values it used and the hash of
the file).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml

from statarb_agent.backtest.accounting import CostModel
from statarb_agent.signals.zscore import SignalParams

HEDGES: Final = ("static", "rolling", "kalman")
NEUTRALITIES: Final = ("dollar", "beta")

_SECTIONS: Final = {
    "walk_forward": {"formation_days", "trading_days"},
    "signal": {"entry_z", "exit_z", "stop_z", "time_stop_days"},
    "hedge": {"default", "variants", "kalman_memory_days"},
    "sizing": {"capital", "gross_exposure", "neutrality"},
    "costs": {
        "cost_bps_per_leg", "sensitivity_bps", "borrow_fee_bps_annual",
        "borrow_day_count",
    },
    "basket": {"det_order", "k_ar_diff"},
    "controls": {
        "synthetic_seed", "random_walk_seed", "n_obs", "half_life", "beta", "alpha",
        "spread_sd", "sigma", "batch_first_seed", "batch_size", "placebo_first_seed",
        "placebo_shuffles",
    },
}


@dataclass(frozen=True)
class ControlsConfig:
    """Simulated controls run next to the real pairs.

    Attributes:
        synthetic_seed: Seed of the single simulated cointegrated pair.
        random_walk_seed: Seed of the single pair of independent random walks.
        n_obs: Rows of every simulated control series.
        half_life, beta, alpha, spread_sd, sigma: Simulator parameters (sigma
            is the daily standard deviation of every random-walk increment).
        batch_first_seed, batch_size: Seeds of the control batches (cointegrated
            pairs and random-walk pairs), first to first + size - 1.
        placebo_first_seed, placebo_shuffles: Seeds and number of shuffled-date
            placebos per real pair.
    """

    synthetic_seed: int
    random_walk_seed: int
    n_obs: int
    half_life: float
    beta: float
    alpha: float
    spread_sd: float
    sigma: float
    batch_first_seed: int
    batch_size: int
    placebo_first_seed: int
    placebo_shuffles: int


@dataclass(frozen=True)
class BacktestConfig:
    """Everything a backtest needs besides prices. See configs/backtest.yaml."""

    formation_days: int
    trading_days: int
    signal: SignalParams
    hedge_default: str
    hedge_variants: tuple[str, ...]
    kalman_memory_days: int
    capital: float
    gross_exposure: float
    neutrality: str
    cost_bps_per_leg: float
    cost_sensitivity_bps: tuple[float, ...]
    borrow_fee_bps_annual: float
    borrow_day_count: int
    basket_det_order: int
    basket_k_ar_diff: int
    controls: ControlsConfig

    def __post_init__(self) -> None:
        if self.formation_days < 60 or self.trading_days < 2:
            raise ValueError("need formation_days >= 60 and trading_days >= 2")
        if self.hedge_default not in HEDGES:
            raise ValueError(f"hedge default must be one of {HEDGES}")
        if not self.hedge_variants or set(self.hedge_variants) - set(HEDGES):
            raise ValueError(f"hedge variants must be chosen from {HEDGES}")
        if len(set(self.hedge_variants)) != len(self.hedge_variants):
            raise ValueError("hedge variants lists a variant twice")
        if self.kalman_memory_days < 2:
            raise ValueError("kalman_memory_days must be at least 2")
        if self.neutrality not in NEUTRALITIES:
            raise ValueError(f"neutrality must be one of {NEUTRALITIES}")
        if not (math.isfinite(self.capital) and self.capital > 0):
            raise ValueError("capital must be finite and > 0")
        if not (math.isfinite(self.gross_exposure) and self.gross_exposure > 0):
            raise ValueError("gross_exposure must be finite and > 0")
        if not self.cost_sensitivity_bps or any(
            not (math.isfinite(c) and c >= 0) for c in self.cost_sensitivity_bps
        ):
            raise ValueError("cost sensitivity levels must be finite and >= 0")
        self.cost_model()  # validates the cost numbers

    def cost_model(self, cost_bps: float | None = None) -> CostModel:
        """The cost model, optionally at another trading-cost level."""
        return CostModel(
            cost_bps_per_leg=self.cost_bps_per_leg if cost_bps is None else cost_bps,
            borrow_fee_bps_annual=self.borrow_fee_bps_annual,
            borrow_day_count=self.borrow_day_count,
        )

    @property
    def kalman_discount(self) -> float:
        """Forgetting factor with an effective memory of kalman_memory_days."""
        return 1.0 - 1.0 / self.kalman_memory_days


def _integer(raw: dict[str, Any], key: str, minimum: int) -> int:
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{key} must be an integer, got {value!r}")
    if value < minimum:
        raise ValueError(f"{key} must be at least {minimum}, got {value}")
    return value


def _number(raw: dict[str, Any], key: str) -> float:
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{key} must be a number, got {value!r}")
    if not math.isfinite(value):
        raise ValueError(f"{key} must be finite, got {value!r}")
    return float(value)


def load_backtest_config(path: Path) -> BacktestConfig:
    """Read and validate configs/backtest.yaml.

    Raises:
        TypeError: If a value has the wrong type.
        ValueError: On unknown or missing sections or keys, or a value out of
            range.
    """
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict) or set(raw) != set(_SECTIONS):
        raise ValueError(f"{path} must have exactly the sections {sorted(_SECTIONS)}")
    for section, keys in _SECTIONS.items():
        if not isinstance(raw[section], dict) or set(raw[section]) != keys:
            raise ValueError(f"{path}: {section} must have exactly the keys {sorted(keys)}")
    walk, signal, hedge = raw["walk_forward"], raw["signal"], raw["hedge"]
    sizing, costs, basket, controls = (
        raw["sizing"], raw["costs"], raw["basket"], raw["controls"],
    )
    if not isinstance(hedge["variants"], list):
        raise TypeError("hedge variants must be a list")
    if not isinstance(costs["sensitivity_bps"], list):
        raise TypeError("costs sensitivity_bps must be a list")
    sensitivity = tuple(
        _number({"sensitivity_bps": v}, "sensitivity_bps")
        for v in costs["sensitivity_bps"]
    )
    return BacktestConfig(
        formation_days=_integer(walk, "formation_days", 1),
        trading_days=_integer(walk, "trading_days", 1),
        signal=SignalParams(
            entry_z=_number(signal, "entry_z"),
            exit_z=_number(signal, "exit_z"),
            stop_z=_number(signal, "stop_z"),
            time_stop_bars=_integer(signal, "time_stop_days", 1),
        ),
        hedge_default=hedge["default"],
        hedge_variants=tuple(hedge["variants"]),
        kalman_memory_days=_integer(hedge, "kalman_memory_days", 1),
        capital=_number(sizing, "capital"),
        gross_exposure=_number(sizing, "gross_exposure"),
        neutrality=sizing["neutrality"],
        cost_bps_per_leg=_number(costs, "cost_bps_per_leg"),
        cost_sensitivity_bps=sensitivity,
        borrow_fee_bps_annual=_number(costs, "borrow_fee_bps_annual"),
        borrow_day_count=_integer(costs, "borrow_day_count", 1),
        basket_det_order=_integer(basket, "det_order", -1),
        basket_k_ar_diff=_integer(basket, "k_ar_diff", 0),
        controls=ControlsConfig(
            synthetic_seed=_integer(controls, "synthetic_seed", 0),
            random_walk_seed=_integer(controls, "random_walk_seed", 0),
            n_obs=_integer(controls, "n_obs", 400),
            half_life=_number(controls, "half_life"),
            beta=_number(controls, "beta"),
            alpha=_number(controls, "alpha"),
            spread_sd=_number(controls, "spread_sd"),
            sigma=_number(controls, "sigma"),
            batch_first_seed=_integer(controls, "batch_first_seed", 0),
            batch_size=_integer(controls, "batch_size", 2),
            placebo_first_seed=_integer(controls, "placebo_first_seed", 0),
            placebo_shuffles=_integer(controls, "placebo_shuffles", 2),
        ),
    )

"""The pair screen: fixed criteria applied to formation-window statistics.

The criteria and where their values come from are in configs/screen.yaml. This
module only compares statistics that stats.pair.pair_stats computed against
those values; it estimates nothing and reads no price data, so it has no asof
of its own.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml

from statarb_agent.stats.pair import PairStats

_KEYS: Final = {
    "eg_pvalue_max",
    "half_life_min",
    "half_life_max",
    "adf_level_pvalue_min",
}


@dataclass(frozen=True)
class ScreenConfig:
    """Contents of configs/screen.yaml, validated.

    Attributes:
        eg_pvalue_max: Engle-Granger p-values must be strictly below this, in
            both directions.
        half_life_min, half_life_max: Inclusive range for the spread half-life
            in bars.
        adf_level_pvalue_min: Each leg's ADF p-value on log-price levels must
            be at or above this (the leg must not look stationary).
    """

    eg_pvalue_max: float
    half_life_min: float
    half_life_max: float
    adf_level_pvalue_min: float


def load_screen(path: Path) -> ScreenConfig:
    """Read and validate a screen config.

    Raises:
        TypeError: If a value is not a number (a YAML boolean or string).
        ValueError: On unknown or missing keys, non-finite values, p-value
            bounds outside (0, 1), or a half-life range that is not
            0 < min < max.
    """
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict) or set(raw) != _KEYS:
        raise ValueError(f"{path} must have exactly the keys {sorted(_KEYS)}")
    values: dict[str, float] = {}
    for key in sorted(_KEYS):
        value = raw[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{key} must be a number, got {value!r}")
        if not math.isfinite(value):
            raise ValueError(f"{key} must be finite, got {value!r}")
        values[key] = float(value)
    for key in ("eg_pvalue_max", "adf_level_pvalue_min"):
        if not 0.0 < values[key] < 1.0:
            raise ValueError(f"{key} must be strictly between 0 and 1")
    if not 0.0 < values["half_life_min"] < values["half_life_max"]:
        raise ValueError("need 0 < half_life_min < half_life_max")
    return ScreenConfig(**values)


@dataclass(frozen=True)
class Criterion:
    """One screen criterion and whether the pair met it."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ScreenResult:
    """Outcome of the screen: passed only if every criterion passed."""

    passed: bool
    criteria: tuple[Criterion, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "criteria": [dataclasses.asdict(c) for c in self.criteria],
        }


def apply_screen(stats: PairStats, screen: ScreenConfig) -> ScreenResult:
    """Compare a pair's statistics against the screen. Every criterion is reported.

    The criteria, in order: eg_both_directions, half_life_in_range,
    legs_not_stationary. A NaN statistic fails its criterion.
    """
    eg = stats.engle_granger
    p_ab, p_ba = eg.a_on_b.pvalue, eg.b_on_a.pvalue
    eg_ok = p_ab < screen.eg_pvalue_max and p_ba < screen.eg_pvalue_max
    eg_detail = (
        f"Engle-Granger p-values {eg.a_on_b.dependent} on {eg.a_on_b.independent} "
        f"{p_ab:.4g}, {eg.b_on_a.dependent} on {eg.b_on_a.independent} {p_ba:.4g}; "
        f"both must be below {screen.eg_pvalue_max:g}"
    )

    fit = stats.spread_ar1
    if fit.mean_reverting and fit.half_life is not None:
        hl_ok = screen.half_life_min <= fit.half_life <= screen.half_life_max
        hl_detail = (
            f"half-life {fit.half_life:.2f} bars; must be in "
            f"[{screen.half_life_min:g}, {screen.half_life_max:g}]"
        )
    else:
        hl_ok = False
        hl_detail = f"no half-life: {fit.reason}"

    adf_a, adf_b = stats.adf_level_a.pvalue, stats.adf_level_b.pvalue
    legs_ok = (
        adf_a >= screen.adf_level_pvalue_min and adf_b >= screen.adf_level_pvalue_min
    )
    legs_detail = (
        f"ADF p-values on log-price levels {stats.label_a} {adf_a:.4g}, "
        f"{stats.label_b} {adf_b:.4g}; both must be at least "
        f"{screen.adf_level_pvalue_min:g} (a unit root is not rejected)"
    )
    criteria = (
        Criterion("eg_both_directions", bool(eg_ok), eg_detail),
        Criterion("half_life_in_range", bool(hl_ok), hl_detail),
        Criterion("legs_not_stationary", bool(legs_ok), legs_detail),
    )
    return ScreenResult(passed=all(c.passed for c in criteria), criteria=criteria)

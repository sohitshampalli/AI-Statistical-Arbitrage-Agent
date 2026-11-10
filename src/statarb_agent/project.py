"""Where things live in a project folder, and the config loaders for it.

Every command works on one project root (the folder holding pyproject.toml,
or a temporary folder in tests). This module is the only place that knows the
layout: configs/, data/, trials/ and reports/.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml

from statarb_agent.provenance import config_hashes
from statarb_agent.sources.tickers import normalise_ticker
from statarb_agent.study import STUDY_CONFIG, to_date
from statarb_agent.trials import LABELS, TRIALS_PATH

CONFIG_NAMES: Final = ("study", "screen", "data", "pairs")


@dataclass(frozen=True)
class Project:
    """Paths inside one project root."""

    root: Path

    @property
    def configs(self) -> Path:
        return self.root / "configs"

    @property
    def study_path(self) -> Path:
        return self.root / STUDY_CONFIG

    @property
    def screen_path(self) -> Path:
        return self.configs / "screen.yaml"

    @property
    def data_config_path(self) -> Path:
        return self.configs / "data.yaml"

    @property
    def pairs_path(self) -> Path:
        return self.configs / "pairs.yaml"

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def trials_path(self) -> Path:
        return self.root / TRIALS_PATH

    @property
    def reports_dir(self) -> Path:
        return self.root / "reports"

    def config_path(self, name: str) -> Path:
        paths = {
            "study": self.study_path,
            "screen": self.screen_path,
            "data": self.data_config_path,
            "pairs": self.pairs_path,
        }
        return paths[name]

    def config_hashes(self, names: tuple[str, ...] = CONFIG_NAMES) -> dict[str, str]:
        """SHA-256 of each named config file."""
        return config_hashes({name: self.config_path(name) for name in names})


# configs/data.yaml ---------------------------------------------------------

_DATA_KEYS: Final = {
    "reference_calendar",
    "download_start",
    "min_obs",
    "max_unmatched_days",
    "max_abs_log_return",
    "max_distribution_fraction",
    "stale_run",
    "pause_seconds",
}


@dataclass(frozen=True)
class DataConfig:
    """Contents of configs/data.yaml, validated. The file explains each value."""

    reference_calendar: str
    download_start: str
    min_obs: int
    max_unmatched_days: int
    max_abs_log_return: float
    max_distribution_fraction: float
    stale_run: int
    pause_seconds: float


def _number(raw: dict[str, Any], key: str, *, integer: bool, minimum: float) -> float:
    value = raw[key]
    wanted = int if integer else (int, float)
    if isinstance(value, bool) or not isinstance(value, wanted):
        kind = "an integer" if integer else "a number"
        raise TypeError(f"{key} must be {kind}, got {value!r}")
    if not math.isfinite(value) or value < minimum:
        raise ValueError(f"{key} must be finite and at least {minimum:g}, got {value!r}")
    return value


def load_data_config(path: Path) -> DataConfig:
    """Read and validate configs/data.yaml.

    Raises:
        TypeError: If a value has the wrong type.
        ValueError: On unknown or missing keys, an invalid ticker or date, or a
            value out of range.
    """
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict) or set(raw) != _DATA_KEYS:
        raise ValueError(f"{path} must have exactly the keys {sorted(_DATA_KEYS)}")
    return DataConfig(
        reference_calendar=normalise_ticker(raw["reference_calendar"]),
        download_start=str(to_date(raw["download_start"]).date()),
        min_obs=int(_number(raw, "min_obs", integer=True, minimum=20)),
        max_unmatched_days=int(
            _number(raw, "max_unmatched_days", integer=True, minimum=0)
        ),
        max_abs_log_return=float(
            _number(raw, "max_abs_log_return", integer=False, minimum=1e-9)
        ),
        max_distribution_fraction=float(
            _number(raw, "max_distribution_fraction", integer=False, minimum=1e-9)
        ),
        stale_run=int(_number(raw, "stale_run", integer=True, minimum=2)),
        pause_seconds=float(_number(raw, "pause_seconds", integer=False, minimum=0.0)),
    )


# configs/pairs.yaml --------------------------------------------------------

_PAIRS_KEYS: Final = {"pairs", "synthetic", "basket"}
_PAIR_KEYS: Final = {"a", "b", "label"}
_SYNTHETIC_KEYS: Final = {
    "name_a", "name_b", "seed", "beta", "alpha", "half_life", "spread_sd",
    "sigma_b", "n_obs",
}


@dataclass(frozen=True)
class DemoPair:
    """One demo pair: two normalised tickers and a label."""

    a: str
    b: str
    label: str


@dataclass(frozen=True)
class SyntheticSpec:
    """Parameters of the simulated demo pair (see data.synthetic)."""

    name_a: str
    name_b: str
    seed: int
    beta: float
    alpha: float
    half_life: float
    spread_sd: float
    sigma_b: float
    n_obs: int


@dataclass(frozen=True)
class PairsConfig:
    """Contents of configs/pairs.yaml, validated."""

    pairs: tuple[DemoPair, ...]
    synthetic: SyntheticSpec
    basket: tuple[str, ...]

    def label_for(self, a: str, b: str) -> str:
        """Label of a demo pair in either order, or "exploratory" if not listed."""
        for pair in self.pairs:
            if {pair.a, pair.b} == {a, b}:
                return pair.label
        return "exploratory"

    def tickers(self) -> tuple[str, ...]:
        """Every real ticker named in the file, in first-seen order."""
        seen: dict[str, None] = {}
        for pair in self.pairs:
            seen[pair.a] = None
            seen[pair.b] = None
        for ticker in self.basket:
            seen[ticker] = None
        return tuple(seen)


def load_pairs(path: Path) -> PairsConfig:
    """Read and validate configs/pairs.yaml.

    Raises:
        TypeError, ValueError: On unknown or missing keys, an invalid ticker,
            a pair of one ticker with itself, a duplicate pair, a label that
            is not case_study or control, or bad synthetic parameters.
    """
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict) or set(raw) != _PAIRS_KEYS:
        raise ValueError(f"{path} must have exactly the keys {sorted(_PAIRS_KEYS)}")
    if not isinstance(raw["pairs"], list) or not raw["pairs"]:
        raise ValueError("pairs must be a non-empty list")
    pairs: list[DemoPair] = []
    for item in raw["pairs"]:
        if not isinstance(item, dict) or set(item) != _PAIR_KEYS:
            raise ValueError(f"each pair needs exactly the keys {sorted(_PAIR_KEYS)}")
        pair = DemoPair(
            a=normalise_ticker(item["a"]), b=normalise_ticker(item["b"]),
            label=item["label"],
        )
        if pair.a == pair.b:
            raise ValueError(f"a pair needs two different tickers, got {pair.a} twice")
        if pair.label not in LABELS or pair.label in ("exploratory", "synthetic"):
            raise ValueError(
                f"demo pair label must be case_study or control, got {pair.label!r}"
            )
        if any({p.a, p.b} == {pair.a, pair.b} for p in pairs):
            raise ValueError(f"pair {pair.a}/{pair.b} is listed twice")
        pairs.append(pair)
    spec = raw["synthetic"]
    if not isinstance(spec, dict) or set(spec) != _SYNTHETIC_KEYS:
        raise ValueError(f"synthetic needs exactly the keys {sorted(_SYNTHETIC_KEYS)}")
    for key in ("name_a", "name_b"):
        if not isinstance(spec[key], str) or not spec[key]:
            raise TypeError(f"synthetic {key} must be a non-empty string")
    synthetic = SyntheticSpec(
        name_a=spec["name_a"],
        name_b=spec["name_b"],
        seed=int(_number(spec, "seed", integer=True, minimum=0)),
        beta=float(_number(spec, "beta", integer=False, minimum=-math.inf)),
        alpha=float(_number(spec, "alpha", integer=False, minimum=-math.inf)),
        half_life=float(_number(spec, "half_life", integer=False, minimum=1e-9)),
        spread_sd=float(_number(spec, "spread_sd", integer=False, minimum=0.0)),
        sigma_b=float(_number(spec, "sigma_b", integer=False, minimum=1e-12)),
        n_obs=int(_number(spec, "n_obs", integer=True, minimum=60)),
    )
    if not isinstance(raw["basket"], list) or len(raw["basket"]) < 3:
        raise ValueError("basket must list at least 3 tickers")
    basket = tuple(normalise_ticker(t) for t in raw["basket"])
    if len(set(basket)) != len(basket):
        raise ValueError("basket lists a ticker twice")
    return PairsConfig(pairs=tuple(pairs), synthetic=synthetic, basket=basket)

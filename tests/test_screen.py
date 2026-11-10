"""Tests for the pair screen: config validation and each criterion's boundary."""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from statarb_agent.data.synthetic import simulate_cointegrated_pair
from statarb_agent.screen import ScreenConfig, apply_screen, load_screen
from statarb_agent.stats.pair import PairStats, pair_stats

REPO_ROOT = Path(__file__).resolve().parents[1]
SCREEN = ScreenConfig(
    eg_pvalue_max=0.05, half_life_min=1.0, half_life_max=63.0,
    adf_level_pvalue_min=0.05,
)
T_FORMATION = 2013
RW_SEEDS = range(7000, 7300)
COINT_SEEDS = range(7000, 7200)
RW_PASS_RATE_MAX = 0.04
COINT_PASS_RATE_MIN = 0.85


@pytest.fixture(scope="module")
def stats() -> PairStats:
    df = simulate_cointegrated_pair(seed=7, n_obs=900)
    return pair_stats(df["log_a"], df["log_b"], "2100-01-01", label_a="AAA",
                      label_b="BBB")


def _with(stats: PairStats, **changes: object) -> PairStats:
    return dataclasses.replace(stats, **changes)


def _eg(stats: PairStats, p_ab: float, p_ba: float) -> PairStats:
    eg = stats.engle_granger
    return _with(stats, engle_granger=dataclasses.replace(
        eg,
        a_on_b=dataclasses.replace(eg.a_on_b, pvalue=p_ab),
        b_on_a=dataclasses.replace(eg.b_on_a, pvalue=p_ba),
    ))


def _half_life(stats: PairStats, value: float | None) -> PairStats:
    fit = stats.spread_ar1
    if value is None:
        fit = dataclasses.replace(fit, mean_reverting=False, half_life=None,
                                  theta=None, mu=None, reason="b = 1.01 >= 1")
    else:
        fit = dataclasses.replace(fit, half_life=value)
    return _with(stats, spread_ar1=fit)


def _legs(stats: PairStats, p_a: float, p_b: float) -> PairStats:
    return _with(
        stats,
        adf_level_a=dataclasses.replace(stats.adf_level_a, pvalue=p_a),
        adf_level_b=dataclasses.replace(stats.adf_level_b, pvalue=p_b),
    )


def _clean(stats: PairStats) -> PairStats:
    """The fixture with every statistic set comfortably inside the screen."""
    return _legs(_half_life(_eg(stats, 0.001, 0.002), 10.0), 0.4, 0.6)


def test_project_config_loads() -> None:
    assert load_screen(REPO_ROOT / "configs" / "screen.yaml") == SCREEN


GOOD = {
    "eg_pvalue_max": "0.05",
    "half_life_min": "1",
    "half_life_max": "63",
    "adf_level_pvalue_min": "0.05",
}


def _yaml(**changes: str | None) -> str:
    """The valid config as YAML text, with keys replaced, added or (None) removed."""
    values = {**GOOD, **changes}
    return "".join(f"{k}: {v}\n" for k, v in values.items() if v is not None)


@pytest.mark.parametrize(
    "text",
    [
        _yaml(adf_level_pvalue_min=None),
        _yaml(extra="1"),
        _yaml(eg_pvalue_max="1.5"),
        _yaml(half_life_min="63"),
        _yaml(half_life_min="0"),
        _yaml(eg_pvalue_max="true"),
        _yaml(eg_pvalue_max="'0.05'"),
        _yaml(eg_pvalue_max=".nan"),
        "- 1\n",
    ],
)
def test_bad_config_raises(tmp_path: Path, text: str) -> None:
    path = tmp_path / "screen.yaml"
    path.write_text(text)
    with pytest.raises((ValueError, TypeError)):
        load_screen(path)


def test_the_valid_text_loads(tmp_path: Path) -> None:
    path = tmp_path / "screen.yaml"
    path.write_text(_yaml())
    assert load_screen(path) == SCREEN


def test_everything_inside_passes(stats: PairStats) -> None:
    result = apply_screen(_clean(stats), SCREEN)
    assert result.passed
    assert [c.name for c in result.criteria] == [
        "eg_both_directions", "half_life_in_range", "legs_not_stationary",
    ]
    assert all(c.passed for c in result.criteria)
    data = result.to_dict()
    assert data["passed"] is True and len(data["criteria"]) == 3


def test_one_direction_is_not_enough(stats: PairStats) -> None:
    for p_ab, p_ba in [(0.001, 0.20), (0.20, 0.001), (0.05, 0.001), (0.001, 0.05)]:
        result = apply_screen(_eg(_clean(stats), p_ab, p_ba), SCREEN)
        assert not result.passed
        assert [c.passed for c in result.criteria] == [False, True, True]
    assert apply_screen(_eg(_clean(stats), 0.0499, 0.0499), SCREEN).passed
    detail = apply_screen(_eg(_clean(stats), 0.001, 0.2), SCREEN).criteria[0].detail
    assert "AAA on BBB" in detail and "BBB on AAA" in detail and "0.2" in detail


def test_half_life_range_is_inclusive(stats: PairStats) -> None:
    for value, expected in [(1.0, True), (63.0, True), (0.99, False), (63.01, False)]:
        result = apply_screen(_half_life(_clean(stats), value), SCREEN)
        assert result.criteria[1].passed is expected
        assert result.passed is expected


def test_not_mean_reverting_fails_with_the_reason(stats: PairStats) -> None:
    result = apply_screen(_half_life(_clean(stats), None), SCREEN)
    assert not result.passed and not result.criteria[1].passed
    assert "b = 1.01 >= 1" in result.criteria[1].detail


def test_a_stationary_looking_leg_fails(stats: PairStats) -> None:
    for p_a, p_b in [(0.01, 0.6), (0.6, 0.01), (0.0499, 0.0499)]:
        result = apply_screen(_legs(_clean(stats), p_a, p_b), SCREEN)
        assert [c.passed for c in result.criteria] == [True, True, False]
    assert apply_screen(_legs(_clean(stats), 0.05, 0.05), SCREEN).passed


def test_nan_statistics_fail(stats: PairStats) -> None:
    nan = math.nan
    assert not apply_screen(_eg(_clean(stats), nan, 0.001), SCREEN).passed
    assert not apply_screen(_half_life(_clean(stats), nan), SCREEN).passed
    assert not apply_screen(_legs(_clean(stats), nan, 0.5), SCREEN).passed


def test_real_statistics_of_a_synthetic_pair(stats: PairStats) -> None:
    """One fixed seed: the two criteria with power pass; the third is reported.

    The legs criterion is not asserted to pass on one seed: ADF rejects a true
    random-walk leg about 6 percent of the time, and seed 7 is such a case at
    T = 2520 (docs/STATUS.md). Its result is checked against the p-values.
    The pass rate is tested across seeds in the slow test below.
    """
    result = apply_screen(stats, SCREEN)
    assert result.criteria[0].passed and result.criteria[1].passed
    expected = stats.adf_level_a.pvalue >= 0.05 and stats.adf_level_b.pvalue >= 0.05
    assert result.criteria[2].passed is expected
    assert result.passed is expected


def _walks(seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    steps = 0.015 * rng.standard_normal((2, T_FORMATION - 1))
    walks = math.log(100.0) + np.concatenate(
        [np.zeros((2, 1)), np.cumsum(steps, axis=1)], axis=1
    )
    idx = pd.bdate_range("2000-01-03", periods=T_FORMATION, name="date")
    return pd.DataFrame({"log_a": walks[0], "log_b": walks[1]}, index=idx)


@pytest.mark.slow
def test_screen_pass_rates_at_the_formation_length(
    report_line: Callable[[str], None],
) -> None:
    """The screen passes few random walks and most true pairs at T = 2013.

    Calibration (seeds 6000 to 6999, scripts/measure_formation_screen.py):
    random walks passed 10 of 1000 (1.0 percent); cointegrated pairs with a
    true half-life of 10 passed 932 of 1000 (93.2 percent).

    This test uses different seeds (7000 onward). Bounds:
    - Random walks, 300 seeds: at most 4 percent. The binomial standard error
      at a rate of 1.0 percent is 0.57 points, so 4 percent is about 5
      standard errors above the calibration rate.
    - Cointegrated, 200 seeds: at least 85 percent. The standard error at
      93.2 percent is 1.78 points, so 85 percent is about 4.6 below.
    """
    rw = [
        apply_screen(pair_stats(d["log_a"], d["log_b"], "2100-01-01"), SCREEN).passed
        for d in (_walks(s) for s in RW_SEEDS)
    ]
    coint = [
        apply_screen(pair_stats(d["log_a"], d["log_b"], "2100-01-01"), SCREEN).passed
        for d in (
            simulate_cointegrated_pair(seed=s, n_obs=T_FORMATION) for s in COINT_SEEDS
        )
    ]
    rw_rate, coint_rate = float(np.mean(rw)), float(np.mean(coint))
    report_line(
        f"screen pass rate at T = {T_FORMATION}: random walks {sum(rw)} of {len(rw)} "
        f"({rw_rate:.1%}), cointegrated half-life 10 {sum(coint)} of {len(coint)} "
        f"({coint_rate:.1%})"
    )
    assert rw_rate <= RW_PASS_RATE_MAX
    assert coint_rate >= COINT_PASS_RATE_MIN

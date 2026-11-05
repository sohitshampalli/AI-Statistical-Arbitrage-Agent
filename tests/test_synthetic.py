"""Tests for the synthetic cointegrated pair simulator.

Distribution checks use a long sample (n = 10_000) and a fixed seed. Each
tolerance is 4 standard errors of the statistic being checked, so a correct
simulator fails it with probability well under 0.1 percent for a fresh seed.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from statarb_agent.data.synthetic import (
    ar1_coefficient_from_half_life,
    simulate_cointegrated_pair,
)

SEED = 12345
N_LONG = 10_000


def test_half_life_mapping_known_values() -> None:
    assert ar1_coefficient_from_half_life(1.0) == 0.5
    assert ar1_coefficient_from_half_life(2.0) == pytest.approx(
        1.0 / math.sqrt(2.0), abs=1e-15
    )


@pytest.mark.parametrize("half_life", [0.5, 1.0, 5.0, 10.0, 63.0, 252.0])
def test_half_life_mapping_round_trip(half_life: float) -> None:
    phi = ar1_coefficient_from_half_life(half_life)
    assert 0.0 < phi < 1.0
    assert math.log(2.0) / (-math.log(phi)) == pytest.approx(half_life, rel=1e-12)


@pytest.mark.parametrize("half_life", [0.0, -1.0, math.inf, math.nan])
def test_half_life_mapping_rejects_bad_input(half_life: float) -> None:
    with pytest.raises(ValueError):
        ar1_coefficient_from_half_life(half_life)


def test_shape_index_and_columns() -> None:
    df = simulate_cointegrated_pair(seed=SEED, n_obs=500)
    assert list(df.columns) == ["log_a", "log_b", "spread"]
    assert len(df) == 500
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.name == "date"
    assert df.index.is_monotonic_increasing and df.index.is_unique
    assert df.index[0] == pd.Timestamp("2000-01-03")
    assert (df.index.day_of_week < 5).all()
    assert all(dtype == np.float64 for dtype in df.dtypes)
    assert np.isfinite(df.to_numpy()).all()


def test_same_seed_is_identical() -> None:
    a = simulate_cointegrated_pair(seed=SEED, n_obs=300)
    b = simulate_cointegrated_pair(seed=SEED, n_obs=300)
    pd.testing.assert_frame_equal(a, b, check_exact=True)


def test_different_seed_differs() -> None:
    a = simulate_cointegrated_pair(seed=SEED, n_obs=300)
    b = simulate_cointegrated_pair(seed=SEED + 1, n_obs=300)
    assert not np.array_equal(a["log_b"].to_numpy(), b["log_b"].to_numpy())
    assert not np.array_equal(a["spread"].to_numpy(), b["spread"].to_numpy())


def test_log_b_unaffected_by_spread_parameters() -> None:
    a = simulate_cointegrated_pair(seed=SEED, n_obs=300, half_life=5.0, spread_sd=0.01)
    b = simulate_cointegrated_pair(seed=SEED, n_obs=300, half_life=40.0, spread_sd=0.05)
    np.testing.assert_array_equal(a["log_b"].to_numpy(), b["log_b"].to_numpy())


def test_cointegrating_identity() -> None:
    beta, alpha = 0.8, -1.2
    df = simulate_cointegrated_pair(seed=SEED, n_obs=1000, beta=beta, alpha=alpha)
    implied = df["log_a"] - alpha - beta * df["log_b"]
    np.testing.assert_allclose(
        implied.to_numpy(), df["spread"].to_numpy(), rtol=0, atol=1e-12
    )


def test_first_log_b_equals_start_level() -> None:
    df = simulate_cointegrated_pair(seed=SEED, n_obs=10, log_p0_b=math.log(50.0))
    assert df["log_b"].iloc[0] == math.log(50.0)


def test_zero_spread_sd_gives_exact_linear_relation() -> None:
    df = simulate_cointegrated_pair(
        seed=SEED, n_obs=200, spread_sd=0.0, beta=2.0, alpha=0.1
    )
    assert (df["spread"] == 0.0).all()
    np.testing.assert_allclose(
        df["log_a"].to_numpy(), 0.1 + 2.0 * df["log_b"].to_numpy(), rtol=0, atol=1e-12
    )


def test_log_b_increment_sd() -> None:
    sigma_b = 0.015
    df = simulate_cointegrated_pair(seed=SEED, n_obs=N_LONG, sigma_b=sigma_b)
    inc = np.diff(df["log_b"].to_numpy())
    # Sample SD of n iid normals has standard error about sigma / sqrt(2 n).
    se = sigma_b / math.sqrt(2 * len(inc))
    assert abs(inc.std(ddof=1) - sigma_b) < 4 * se
    # Mean increment is zero (no drift); standard error sigma / sqrt(n).
    assert abs(inc.mean()) < 4 * sigma_b / math.sqrt(len(inc))


@pytest.mark.parametrize("half_life", [5.0, 10.0, 20.0])
def test_spread_ar1_structure(half_life: float) -> None:
    spread_sd = 0.02
    df = simulate_cointegrated_pair(
        seed=SEED, n_obs=N_LONG, half_life=half_life, spread_sd=spread_sd
    )
    s = df["spread"].to_numpy()
    phi = ar1_coefficient_from_half_life(half_life)
    n = len(s) - 1

    # Lag-1 autocorrelation estimates phi with standard error sqrt((1 - phi^2) / n).
    r1 = np.corrcoef(s[1:], s[:-1])[0, 1]
    assert abs(r1 - phi) < 4 * math.sqrt((1 - phi**2) / n)

    # Innovations S[t] - phi S[t-1] are iid N(0, eps_sd^2).
    eps_sd = spread_sd * math.sqrt(1 - phi**2)
    innov = s[1:] - phi * s[:-1]
    assert abs(innov.std(ddof=1) - eps_sd) < 4 * eps_sd / math.sqrt(2 * n)
    assert abs(innov.mean()) < 4 * eps_sd / math.sqrt(n)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"seed": -1},
        {"seed": 1.5},
        {"seed": True},
        {"seed": 0, "n_obs": 2},
        {"seed": 0, "n_obs": 10.0},
        {"seed": 0, "half_life": 0.0},
        {"seed": 0, "half_life": -3.0},
        {"seed": 0, "spread_sd": -0.01},
        {"seed": 0, "spread_sd": math.nan},
        {"seed": 0, "sigma_b": 0.0},
        {"seed": 0, "beta": math.inf},
        {"seed": 0, "alpha": math.nan},
    ],
)
def test_rejects_bad_input(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        simulate_cointegrated_pair(**kwargs)

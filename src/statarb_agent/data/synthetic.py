"""Synthetic cointegrated pair with known beta, intercept and spread half-life.

Model (one bar per business day, dt = 1):

    p_B[0] = log_p0_b
    p_B[t] = p_B[t-1] + sigma_b * eta[t]                  (driftless random walk)

    S[t]   = phi * S[t-1] + eps_sd * e[t]                 (exact OU discretisation)
    phi    = exp(-theta),  theta = ln(2) / half_life,  so phi = 2 ** (-1 / half_life)
    eps_sd = spread_sd * sqrt(1 - phi**2)                 (spread_sd is the stationary SD)
    S[0]   = spread_sd * e[0]                             (stationary start, no burn-in)

    p_A[t] = alpha + beta * p_B[t] + S[t]

eta and e are independent iid N(0, 1). They come from one numpy Generator seeded
with `seed`: first all of eta (n_obs - 1 draws), then all of e (n_obs draws). That
fixed order means changing half_life or spread_sd leaves log_b unchanged for a
given seed.

This module generates data only. It computes no statistics from data.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

MIN_OBS = 3


def ar1_coefficient_from_half_life(half_life: float) -> float:
    """Return the AR(1) coefficient phi = 2 ** (-1 / half_life) for dt = 1.

    This is the exact discretisation of an OU process with theta = ln(2) / half_life.
    The inverse is half_life = ln(2) / (-ln(phi)).
    """
    if not (math.isfinite(half_life) and half_life > 0):
        raise ValueError(f"half_life must be finite and > 0, got {half_life!r}")
    return 2.0 ** (-1.0 / half_life)


def simulate_cointegrated_pair(
    *,
    seed: int,
    beta: float = 1.5,
    alpha: float = 0.3,
    half_life: float = 10.0,
    spread_sd: float = 0.02,
    sigma_b: float = 0.015,
    n_obs: int = 2520,
    log_p0_b: float = math.log(100.0),
    start: str = "2000-01-03",
) -> pd.DataFrame:
    """Simulate log prices of a cointegrated pair with known parameters.

    Args:
        seed: Non-negative integer seed for numpy.random.default_rng. Required.
        beta: True hedge ratio of log_a on log_b.
        alpha: True intercept of log_a on log_b.
        half_life: True spread half-life in bars (business days).
        spread_sd: Stationary standard deviation of the spread. 0 gives an exact
            linear relation with no spread.
        sigma_b: Daily standard deviation of log_b increments.
        n_obs: Number of rows.
        log_p0_b: Value of log_b on the first row.
        start: First date of the business-day index.

    Returns:
        DataFrame indexed by a business-day DatetimeIndex named "date", with float
        columns "log_a", "log_b" and "spread" (the true, unobservable spread S).
    """
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or seed < 0:
        raise ValueError(f"seed must be a non-negative integer, got {seed!r}")
    if (
        isinstance(n_obs, bool)
        or not isinstance(n_obs, (int, np.integer))
        or n_obs < MIN_OBS
    ):
        raise ValueError(f"n_obs must be an integer >= {MIN_OBS}, got {n_obs!r}")
    for name, value in (("beta", beta), ("alpha", alpha), ("log_p0_b", log_p0_b)):
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite, got {value!r}")
    if not (math.isfinite(spread_sd) and spread_sd >= 0):
        raise ValueError(f"spread_sd must be finite and >= 0, got {spread_sd!r}")
    if not (math.isfinite(sigma_b) and sigma_b > 0):
        raise ValueError(f"sigma_b must be finite and > 0, got {sigma_b!r}")
    phi = ar1_coefficient_from_half_life(half_life)

    rng = np.random.default_rng(seed)
    eta = rng.standard_normal(n_obs - 1)
    e = rng.standard_normal(n_obs)

    log_b = np.empty(n_obs)
    log_b[0] = log_p0_b
    log_b[1:] = log_p0_b + np.cumsum(sigma_b * eta)

    eps_sd = spread_sd * math.sqrt(1.0 - phi * phi)
    spread = np.empty(n_obs)
    spread[0] = spread_sd * e[0]
    for t in range(1, n_obs):
        spread[t] = phi * spread[t - 1] + eps_sd * e[t]

    log_a = alpha + beta * log_b + spread

    index = pd.bdate_range(start=start, periods=n_obs, name="date")
    return pd.DataFrame({"log_a": log_a, "log_b": log_b, "spread": spread}, index=index)

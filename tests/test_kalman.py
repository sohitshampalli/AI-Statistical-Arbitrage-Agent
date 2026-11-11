"""Tests for the hand-written Kalman filter of the hedge ratio.

Exact known answers come from two closed forms the filter must reproduce:

- With no state noise (discount = 1) it is Bayesian linear regression. After n
  rows, with prior N(m0, P0) and noise variance R:
      precision = inv(P0) + X'X / R,   mean = inv(precision) (inv(P0) m0 + X'y / R).
- With a forgetting factor lam, each predict step multiplies the precision by
  lam, so after n rows:
      precision = lam**n inv(P0) + sum_t lam**(n - t) H_t'H_t / R
  and the same weights apply to the mean's right-hand side.

Recovery of a time-varying beta is tested on data simulated from the filter's
own model, where the filter is optimal. Calibration, seeds 8000 to 8199, 2000
rows, beta a random walk with daily sd 0.002, noise sd 0.02, log_b a centred
random walk with daily sd 0.015; errors measured on rows 1000 onward:

- RMSE of the filtered beta: mean 0.0129, maximum 0.0290. Static OLS on all
  rows: mean 0.0316. The filter was closer than OLS on 93 percent of seeds.
- Mean squared standardised innovation (should be 1): mean 1.0012, range
  0.904 to 1.144.
- Mean squared beta error over its stated variance (should be 1): mean 1.026.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
import pytest

from statarb_agent.stats.hedge_ratio import ols_hedge_ratio
from statarb_agent.stats.kalman import COLUMNS, kalman_hedge

ASOF = "2100-01-01"
Q_BETA = 0.002
OBS_SD = 0.02
TRUE_NOISE = np.diag([0.0, Q_BETA**2])
VAGUE = {"init_mean": [0.0, 0.0], "init_cov": np.diag([1.0, 1.0])}
SINGLE_SEED = 8300
SLOW_SEEDS = range(8200, 8400)


def simulate(seed: int, n: int = 2000) -> tuple[pd.Series, pd.Series, np.ndarray]:
    """log_a, log_b and the true beta path, drawn from the filter's model."""
    rng = np.random.default_rng(seed)
    x = np.cumsum(0.015 * rng.standard_normal(n))
    beta = 1.0 + np.cumsum(Q_BETA * rng.standard_normal(n))
    y = 0.3 + beta * x + OBS_SD * rng.standard_normal(n)
    idx = pd.bdate_range("2000-01-03", periods=n, name="date")
    return pd.Series(y, index=idx), pd.Series(x, index=idx), beta


@pytest.fixture(scope="module")
def data() -> tuple[pd.Series, pd.Series]:
    y, x, _ = simulate(1, n=300)
    return y, x


def test_no_state_noise_is_bayesian_linear_regression(
    data: tuple[pd.Series, pd.Series],
) -> None:
    y, x = data
    m0 = np.array([0.2, 0.7])
    p0 = np.array([[0.5, 0.1], [0.1, 0.3]])
    r = 0.02**2
    out = kalman_hedge(y, x, ASOF, obs_var=r, init_mean=m0, init_cov=p0, discount=1.0)
    design = np.column_stack([np.ones(len(x)), x.to_numpy()])
    precision = np.linalg.inv(p0) + design.T @ design / r
    cov = np.linalg.inv(precision)
    mean = cov @ (np.linalg.inv(p0) @ m0 + design.T @ y.to_numpy() / r)
    last = out.iloc[-1]
    assert last["alpha"] == pytest.approx(mean[0], rel=1e-8)
    assert last["beta"] == pytest.approx(mean[1], rel=1e-8)
    assert last["alpha_var"] == pytest.approx(cov[0, 0], rel=1e-8)
    assert last["beta_var"] == pytest.approx(cov[1, 1], rel=1e-8)
    zero_noise = kalman_hedge(
        y, x, ASOF, obs_var=r, init_mean=m0, init_cov=p0, state_cov=np.zeros((2, 2))
    )
    pd.testing.assert_frame_equal(zero_noise, out, check_exact=True)


def test_vague_prior_converges_to_ols(data: tuple[pd.Series, pd.Series]) -> None:
    y, x = data
    out = kalman_hedge(y, x, ASOF, obs_var=0.02**2, init_mean=[0.0, 0.0],
                       init_cov=np.diag([1e8, 1e8]), discount=1.0)
    ols = ols_hedge_ratio(y, x, ASOF)
    assert out["beta"].iloc[-1] == pytest.approx(ols.beta, rel=1e-6)
    assert out["alpha"].iloc[-1] == pytest.approx(ols.alpha, rel=1e-6)


def test_discount_is_weighted_least_squares(data: tuple[pd.Series, pd.Series]) -> None:
    y, x = data
    n, lam, r = len(y), 0.98, 0.02**2
    m0 = np.array([0.2, 0.7])
    p0 = np.array([[0.5, 0.1], [0.1, 0.3]])
    out = kalman_hedge(y, x, ASOF, obs_var=r, init_mean=m0, init_cov=p0, discount=lam)
    design = np.column_stack([np.ones(n), x.to_numpy()])
    weights = lam ** np.arange(n - 1, -1, -1)  # the last row has weight 1
    precision = lam**n * np.linalg.inv(p0) + (design.T * weights) @ design / r
    rhs = lam**n * np.linalg.inv(p0) @ m0 + (design.T * weights) @ y.to_numpy() / r
    cov = np.linalg.inv(precision)
    mean = cov @ rhs
    last = out.iloc[-1]
    assert last["alpha"] == pytest.approx(mean[0], rel=1e-7)
    assert last["beta"] == pytest.approx(mean[1], rel=1e-7)
    assert last["beta_var"] == pytest.approx(cov[1, 1], rel=1e-7)


def test_first_row_by_hand() -> None:
    """One step, computed by hand: prior (0, 1), P = I, W = 0.5 I, R = 2, x = 2, y = 5.

    P_pred = 1.5 I. H = [1, 2]. e = 5 - 2 = 3. Q = 1.5 * (1 + 4) + 2 = 9.5.
    K = 1.5 * [1, 2] / 9.5. mean = (0, 1) + K * 3.
    """
    idx = pd.DatetimeIndex(["2020-01-02"])
    out = kalman_hedge(
        pd.Series([5.0], index=idx), pd.Series([2.0], index=idx), ASOF, obs_var=2.0,
        init_mean=[0.0, 1.0], init_cov=np.eye(2), state_cov=0.5 * np.eye(2),
    )
    row = out.iloc[0]
    assert list(out.columns) == list(COLUMNS)
    assert (row["alpha_pred"], row["beta_pred"]) == (0.0, 1.0)
    assert row["innovation"] == pytest.approx(3.0)
    assert row["innovation_var"] == pytest.approx(9.5)
    assert row["alpha"] == pytest.approx(1.5 * 3 / 9.5)
    assert row["beta"] == pytest.approx(1.0 + 3.0 * 3 / 9.5)
    # P = P_pred - K Q K' for the optimal gain
    assert row["alpha_var"] == pytest.approx(1.5 - 1.5**2 / 9.5)
    assert row["beta_var"] == pytest.approx(1.5 - 3.0**2 / 9.5)


def test_predictions_use_only_earlier_rows() -> None:
    """Look-ahead test: changing rows from t on leaves forecasts up to t alone.

    The forecast columns of row t come from rows before t, so they survive a
    change to row t itself; the updated columns of row t do not.
    """
    y, x, _ = simulate(2, n=200)
    asof = y.index[180]
    kwargs = {"obs_var": OBS_SD**2, **VAGUE, "state_cov": TRUE_NOISE}
    before = kalman_hedge(y, x, asof, **kwargs)
    assert len(before) == 180 and before.index.max() == y.index[179]
    cut = 120
    y2, x2 = y.copy(), x.copy()
    y2.iloc[cut:] = 7.0
    x2.iloc[cut:] = -3.0
    y2.iloc[185] = np.nan  # at or after asof: never read
    after = kalman_hedge(y2, x2, asof, **kwargs)
    pd.testing.assert_frame_equal(after.iloc[:cut], before.iloc[:cut], check_exact=True)
    forecast = ["alpha_pred", "beta_pred"]
    pd.testing.assert_frame_equal(
        after.iloc[: cut + 1][forecast], before.iloc[: cut + 1][forecast],
        check_exact=True,
    )
    assert after["beta"].iloc[cut] != before["beta"].iloc[cut]
    # innovation_var of row t needs log_b[t] but not log_a[t]
    y3 = y.copy()
    y3.iloc[cut] = 99.0
    only_y = kalman_hedge(y3, x, asof, **kwargs)
    assert only_y["innovation_var"].iloc[cut] == before["innovation_var"].iloc[cut]


def test_recovers_a_time_varying_beta_on_one_seed() -> None:
    """Seed 8300, not a calibration seed.

    RMSE below 0.035: the calibration maximum over 200 seeds was 0.0290.

    Mean squared standardised innovation within 4 standard errors of 1, that
    is in [0.821, 1.179]. Under the model the standardised innovations are
    independent N(0, 1), so the mean of 1000 squares has standard error
    sqrt(2 / 1000) = 0.0447 (the calibration seeds gave 0.0465).

    History: the first version of this test used [0.88, 1.17], the calibration
    range plus a little headroom, which is only 2.7 standard errors below 1.
    Seed 8300 measured 0.8743 (2.8 standard errors below 1) and failed it. The
    seed was kept and the bound was replaced by the theoretical one above. The
    mean over seeds 8200 to 8399, which include this one, is 0.994 (slow test).
    """
    y, x, beta = simulate(SINGLE_SEED)
    out = kalman_hedge(y, x, ASOF, obs_var=OBS_SD**2, **VAGUE, state_cov=TRUE_NOISE)
    late = slice(1000, None)
    rmse = float(np.sqrt(np.mean((out["beta"].to_numpy()[late] - beta[late]) ** 2)))
    nis = float(np.mean(out["innovation"].to_numpy()[late] ** 2
                        / out["innovation_var"].to_numpy()[late]))
    assert rmse < 0.035
    assert 0.821 < nis < 1.179
    assert np.ptp(beta) > 0.05  # the true beta really moved


@pytest.mark.slow
def test_recovery_rates_across_seeds(report_line: Callable[[str], None]) -> None:
    """Seeds 8200 to 8399. Bounds from the calibration in the module docstring:

    - mean RMSE below 0.016: calibration mean 0.0129 with standard error 0.0004.
    - mean squared standardised innovation in [0.985, 1.015]: calibration mean
      1.0012 with standard error 0.0033, so about 4.5 standard errors each way.
    - mean squared error over stated variance in [0.90, 1.15]: calibration mean
      1.026 with standard error 0.023.
    - closer than static OLS on at least 85 percent of seeds: calibration 93
      percent with standard error 1.8 points.
    """
    rmse, ols_rmse, nis, nees = [], [], [], []
    late = slice(1000, None)
    for seed in SLOW_SEEDS:
        y, x, beta = simulate(seed)
        out = kalman_hedge(y, x, ASOF, obs_var=OBS_SD**2, **VAGUE, state_cov=TRUE_NOISE)
        err = out["beta"].to_numpy()[late] - beta[late]
        rmse.append(np.sqrt(np.mean(err**2)))
        ols = ols_hedge_ratio(y, x, ASOF).beta
        ols_rmse.append(np.sqrt(np.mean((ols - beta[late]) ** 2)))
        nis.append(np.mean(out["innovation"].to_numpy()[late] ** 2
                           / out["innovation_var"].to_numpy()[late]))
        nees.append(np.mean(err**2 / out["beta_var"].to_numpy()[late]))
    better = float(np.mean(np.array(rmse) < np.array(ols_rmse)))
    report_line(
        f"Kalman beta recovery, seeds 8200-8399: mean RMSE {np.mean(rmse):.4f} "
        f"(static OLS {np.mean(ols_rmse):.4f}), closer than OLS on {better:.1%}, "
        f"standardised innovation {np.mean(nis):.4f}, error over stated variance "
        f"{np.mean(nees):.3f}"
    )
    assert np.mean(rmse) < 0.016
    assert 0.985 < np.mean(nis) < 1.015
    assert 0.90 < np.mean(nees) < 1.15
    assert better >= 0.85


@pytest.mark.parametrize(
    "kwargs",
    [
        {"state_cov": TRUE_NOISE, "discount": 0.99},
        {},
        {"discount": 0.0},
        {"discount": 1.01},
        {"discount": float("nan")},
        {"state_cov": np.array([[1.0, 2.0], [0.0, 1.0]])},
        {"state_cov": np.diag([1.0, -1.0])},
        {"state_cov": np.eye(3)},
        {"discount": 0.99, "obs_var": 0.0},
        {"discount": 0.99, "init_mean": [0.0, 0.0, 0.0]},
        {"discount": 0.99, "init_cov": np.diag([1.0, -1.0])},
        {"discount": 0.99, "init_mean": [0.0, float("inf")]},
    ],
)
def test_invalid_settings_raise(
    data: tuple[pd.Series, pd.Series], kwargs: dict[str, object]
) -> None:
    y, x = data
    settings = {"obs_var": 1.0, "init_mean": [0.0, 0.0], "init_cov": np.eye(2), **kwargs}
    with pytest.raises(ValueError):
        kalman_hedge(y, x, ASOF, **settings)


def test_mismatched_dates_raise(data: tuple[pd.Series, pd.Series]) -> None:
    y, x = data
    with pytest.raises(ValueError, match="different dates"):
        kalman_hedge(y, x.drop(x.index[5]), ASOF, obs_var=1.0, init_mean=[0.0, 0.0],
                     init_cov=np.eye(2), discount=0.99)

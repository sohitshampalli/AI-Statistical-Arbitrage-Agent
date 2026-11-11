"""Kalman filter for a time-varying hedge ratio, written by hand in numpy.

Model (one bar per row, t = 1, 2, ...):

    state        theta[t] = (alpha[t], beta[t])
    transition   theta[t] = theta[t-1] + w[t],            w[t] ~ N(0, W[t])
    observation  log_a[t] = alpha[t] + beta[t] * log_b[t] + v[t],   v[t] ~ N(0, R)

Both coefficients follow a random walk. Each row does two steps:

    predict   m_pred = m                  P_pred = P + W[t]
    update    H   = [1, log_b[t]]
              e   = log_a[t] - H . m_pred          (innovation)
              Q   = H P_pred H' + R                (innovation variance)
              K   = P_pred H' / Q                  (gain)
              m   = m_pred + K e
              P   = (I - K H) P_pred (I - K H)' + K R K'    (Joseph form)

m_pred and P_pred for row t use rows before t only, so alpha_pred[t] and
beta_pred[t] are forecasts available at the close of t - 1. The innovation
variance Q[t] also uses row t's log_b (through H), and the innovation e[t] uses
both of row t's prices. Nothing on row t uses a later row. A signal computed
from e[t] and Q[t] is therefore known at the close of bar t, like any signal in
this project, and is acted on at bar t + 1.

The state noise W[t] is given in one of two ways:

- `state_cov`: a fixed 2 x 2 matrix W.
- `discount`: a number lam in (0, 1]; then P_pred = P / lam, which is
  W[t] = P (1 - lam) / lam. This is recursive least squares with a forgetting
  factor: after many rows the estimate is the least-squares fit with weight
  lam ** k on the row k bars back, an effective memory of 1 / (1 - lam) rows.
  lam = 1 is ordinary recursive least squares (no state noise).

The model treats v[t] as white noise. A real spread is persistent, so R should
be the variance of the whole spread, not of its day-to-day change; otherwise the
filter chases the spread with alpha and removes the signal. For the same reason
the noise settings are not fitted by maximum likelihood here: likelihood would
explain the spread's persistence as state noise.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from statarb_agent.stats._asof import paired_rows_before

COLUMNS = (
    "alpha_pred",
    "beta_pred",
    "innovation",
    "innovation_var",
    "alpha",
    "beta",
    "alpha_var",
    "beta_var",
)


def _symmetric_psd(matrix: np.ndarray, name: str) -> np.ndarray:
    out = np.asarray(matrix, dtype=float)
    if out.shape != (2, 2) or not np.isfinite(out).all():
        raise ValueError(f"{name} must be a finite 2 x 2 matrix")
    if not np.allclose(out, out.T, rtol=1e-12, atol=0.0):
        raise ValueError(f"{name} must be symmetric")
    scale = max(1.0, float(np.abs(out).max()))
    if np.linalg.eigvalsh(out).min() < -1e-12 * scale:
        raise ValueError(f"{name} must be positive semi-definite")
    return out


def kalman_hedge(
    log_a: pd.Series,
    log_b: pd.Series,
    asof: pd.Timestamp | str,
    *,
    obs_var: float,
    init_mean: np.ndarray,
    init_cov: np.ndarray,
    state_cov: np.ndarray | None = None,
    discount: float | None = None,
) -> pd.DataFrame:
    """Filter log_a = alpha[t] + beta[t] * log_b + noise on rows before `asof`.

    Args:
        log_a, log_b: Log prices with identical dates before `asof`.
        asof: As-of date. Only rows strictly before it are used or returned.
        obs_var: R, the observation noise variance. Must be > 0.
        init_mean: (alpha, beta) believed just before the first row.
        init_cov: 2 x 2 covariance of that belief. The predict step is applied
            to it for the first row like for every other row.
        state_cov: Fixed state noise covariance W (2 x 2). Give this or
            `discount`, not both.
        discount: Forgetting factor lam in (0, 1]; see the module docstring.

    Returns:
        DataFrame indexed like the rows before `asof`, with columns:
        alpha_pred, beta_pred: state forecast for row t from rows before t.
        innovation: log_a[t] minus its forecast.
        innovation_var: variance Q[t] of that innovation given rows before t
            and row t's log_b.
        alpha, beta: state after row t's update.
        alpha_var, beta_var: diagonal of the covariance after the update.

    Raises:
        ValueError: On invalid noise settings, or for any reason
            paired_rows_before raises.
    """
    if (state_cov is None) == (discount is None):
        raise ValueError("give exactly one of state_cov and discount")
    if not (math.isfinite(obs_var) and obs_var > 0.0):
        raise ValueError(f"obs_var must be finite and > 0, got {obs_var!r}")
    mean = np.asarray(init_mean, dtype=float)
    if mean.shape != (2,) or not np.isfinite(mean).all():
        raise ValueError("init_mean must be two finite numbers (alpha, beta)")
    cov = _symmetric_psd(init_cov, "init_cov")
    if state_cov is not None:
        noise = _symmetric_psd(state_cov, "state_cov")
    elif not (math.isfinite(discount) and 0.0 < discount <= 1.0):
        raise ValueError(f"discount must be in (0, 1], got {discount!r}")

    a, b = paired_rows_before(log_a, log_b, asof)
    y = a.to_numpy(dtype=float)
    x = b.to_numpy(dtype=float)
    n = len(y)
    out = np.empty((n, len(COLUMNS)))
    identity = np.eye(2)
    for t in range(n):
        # Predict: uses nothing from row t.
        cov_pred = cov + noise if state_cov is not None else cov / discount
        h = np.array([1.0, x[t]])
        # Update with row t.
        innovation = y[t] - h @ mean
        ph = cov_pred @ h
        innovation_var = float(h @ ph) + obs_var
        gain = ph / innovation_var
        mean_pred = mean
        mean = mean + gain * innovation
        factor = identity - np.outer(gain, h)
        cov = factor @ cov_pred @ factor.T + obs_var * np.outer(gain, gain)
        out[t] = (
            mean_pred[0], mean_pred[1], innovation, innovation_var,
            mean[0], mean[1], cov[0, 0], cov[1, 1],
        )
    return pd.DataFrame(out, index=a.index, columns=list(COLUMNS))

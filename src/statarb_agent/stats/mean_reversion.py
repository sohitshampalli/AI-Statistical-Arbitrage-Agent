"""AR(1) fit of a spread, with OU parameters and half-life.

Model: S[t] = a + b * S[t-1] + e[t], fitted by OLS on rows strictly before an
as-of date. If 0 < b < 1:

    theta = -ln(b) / dt,  mu = a / (1 - b),  half_life = ln(2) / theta

half_life is in the same time unit as dt (bars when dt = 1).

Small-sample bias: the OLS AR coefficient is biased downward, so the half-life is
too. Measured on the in-sample spread with a true half-life of 10 bars: mean
relative error -3.3 percent at T = 2520 (400 seeds) and -0.7 percent at T = 10,000
(200 seeds). This is documented and deliberately not corrected.

In-sample caveat: if `spread` is built from a hedge ratio estimated on the same
rows, this is an in-sample fit. That is how the Phase 1 gate is defined; it is not
an out-of-sample estimate.

0 < b < 1 is a precondition for computing OU parameters, not evidence of mean
reversion. On pure random walks b was below 1 in 95.9 percent of seeds at T = 2520
(seeds 0 to 999), because the same downward bias pulls b under 1. Use the unit
root and cointegration tests to decide whether a spread mean-reverts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

from statarb_agent.stats._asof import rows_before

AR1_MIN_OBS = 20


@dataclass(frozen=True)
class AR1Fit:
    """OLS AR(1) fit and, when 0 < b < 1, the implied OU parameters.

    Attributes:
        a: Intercept.
        b: AR coefficient.
        resid_sd: Residual standard deviation (degrees of freedom nobs - 2).
        nobs: Observations in the regression (rows used minus one).
        mean_reverting: True if and only if 0 < b < 1.
        theta: Mean-reversion speed, or None if not mean-reverting.
        mu: Long-run mean, or None if not mean-reverting.
        half_life: ln(2) / theta, or None if not mean-reverting.
        reason: Why the fit is not mean-reverting, or None if it is.
    """

    a: float
    b: float
    resid_sd: float
    nobs: int
    mean_reverting: bool
    theta: float | None
    mu: float | None
    half_life: float | None
    reason: str | None


def _ou_parameters(
    a: float, b: float, dt: float
) -> tuple[bool, float | None, float | None, float | None, str | None]:
    """Apply the rule of brief section 5 to AR(1) coefficients. Pure, no data.

    Args:
        a: AR(1) intercept.
        b: AR(1) coefficient.
        dt: Time step between rows.

    Returns:
        (mean_reverting, theta, mu, half_life, reason). mean_reverting is True
        exactly when 0 < b < 1, with no tolerance around either end; otherwise
        theta, mu and half_life are None and reason says why.
    """
    if b >= 1.0:
        return False, None, None, None, f"b = {b:.6g} >= 1: not mean-reverting"
    if b <= 0.0:
        return False, None, None, None, f"b = {b:.6g} <= 0: not mean-reverting"
    theta = -math.log(b) / dt
    return True, theta, a / (1.0 - b), math.log(2.0) / theta, None


def fit_ar1(
    spread: pd.Series,
    asof: pd.Timestamp | str,
    *,
    dt: float = 1.0,
    min_obs: int = AR1_MIN_OBS,
) -> AR1Fit:
    """Fit S[t] = a + b * S[t-1] + e[t] on rows of `spread` strictly before `asof`.

    This is a pure estimator. 0 < b < 1 is necessary but not sufficient for mean
    reversion, so mean_reverting=True does not mean the spread mean-reverts. The
    screening decision belongs to the cointegration tests plus a half-life range,
    to be decided in Phase 2.

    A noiseless linear trend has a true b of exactly 1, but floating-point
    rounding in OLS can land just below 1 and give an astronomical half-life
    (for example about 6e15 bars on 0, 1, ..., 99). No tolerance is applied.

    Args:
        spread: Spread values with a DatetimeIndex.
        asof: As-of date. Only rows dated strictly before it are used.
        dt: Time step between rows. Must be finite and > 0.
        min_obs: Minimum rows required before `asof`.

    Returns:
        AR1Fit with plain Python floats, ints and bools.

    Raises:
        ValueError: If dt is invalid, for any reason rows_before raises
            ValueError, or if the series before `asof` is constant, because
            the regression is then singular.
    """
    if not (math.isfinite(dt) and dt > 0):
        raise ValueError(f"dt must be finite and > 0, got {dt!r}")
    values = rows_before(spread, asof, min_obs=min_obs).to_numpy(dtype=float)
    lagged = values[:-1]
    if np.ptp(lagged) == 0.0:
        raise ValueError("spread is constant before asof; the regression is singular")

    exog = sm.add_constant(lagged, prepend=True, has_constant="raise")
    res = sm.OLS(values[1:], exog).fit()
    a = float(res.params[0])
    b = float(res.params[1])
    mean_reverting, theta, mu, half_life, reason = _ou_parameters(a, b, dt)
    return AR1Fit(
        a=a,
        b=b,
        resid_sd=math.sqrt(float(res.mse_resid)),
        nobs=len(values) - 1,
        mean_reverting=mean_reverting,
        theta=theta,
        mu=mu,
        half_life=half_life,
        reason=reason,
    )

"""Property test that closes the Phase 1 gate: recovery across seeds and parameters.

Strategy: seed in [0, 2**32), beta in [0.5, 2], half-life in [5, 15], at
T = 10,000 with default alpha, spread_sd and sigma_b. Pipeline as in the gate:
OLS hedge ratio, spread and AR(1) on the same rows (an in-sample fit).

Measured before the bounds were fixed, through this same code. Worst value of
each asserted quantity (bound in brackets):

300 independent uniform draws (numpy generator, seed 20261106):
- Engle-Granger p, A on B: 6.975e-21 at seed 2959264301, beta 1.9057, HL 11.3771 (0.01)
- Engle-Granger p, B on A: 7.299e-21 at the same draw (0.01)
- abs(beta_hat - beta): 0.01063 at seed 1188684272, beta 1.5996, HL 7.9939 (0.03)
- abs(HL_hat / HL - 1): 0.2000 at seed 592533811, beta 1.0223, HL 14.6463 (0.25)

200 draws from this hypothesis strategy, derandomize=False:
- Engle-Granger p, A on B: 1.321e-25 at seed 474, beta 1.0, HL 10.0 (0.01)
- Engle-Granger p, B on A: 1.41e-25 at the same draw (0.01)
- abs(beta_hat - beta): 0.00722 at seed 3718, beta 0.8292, HL 7.8766 (0.03)
- abs(HL_hat / HL - 1): 0.1307 at seed 575453111, beta 1.0, HL 13.7345 (0.25)

No draw out of 500 reached a bound. The half-life bound has the least headroom.

ADF on levels and Engle-Granger on independent walks are left out on purpose.
They are size properties that fail on about 5 percent of seeds by design, so
they stay in the slow rate tests.

With derandomize=True the examples are fixed by a hash of the test function, so
they change if Hypothesis, Python or this function changes. About 0.6 s per
example, so this test is marked slow.
"""

from __future__ import annotations

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from statarb_agent.data.synthetic import simulate_cointegrated_pair
from statarb_agent.stats.cointegration import engle_granger
from statarb_agent.stats.hedge_ratio import ols_hedge_ratio, spread
from statarb_agent.stats.mean_reversion import fit_ar1

ASOF = pd.Timestamp("2100-01-01")  # after every simulated date
N_OBS = 10_000
EG_P_MAX = 0.01
BETA_TOL = 0.03
HALF_LIFE_TOL = 0.25


@pytest.mark.slow
@settings(max_examples=25, derandomize=True, database=None, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=2**32 - 1),
    beta=st.floats(min_value=0.5, max_value=2.0),
    half_life=st.floats(min_value=5.0, max_value=15.0),
)
def test_recovers_truth_across_seeds_and_parameters(
    seed: int, beta: float, half_life: float
) -> None:
    df = simulate_cointegrated_pair(
        seed=seed, n_obs=N_OBS, beta=beta, half_life=half_life
    )

    eg = engle_granger(df["log_a"], df["log_b"], ASOF)
    assert eg.a_on_b.pvalue < EG_P_MAX
    assert eg.b_on_a.pvalue < EG_P_MAX

    hedge = ols_hedge_ratio(df["log_a"], df["log_b"], ASOF)
    assert abs(hedge.beta - beta) < BETA_TOL

    fit = fit_ar1(spread(df["log_a"], df["log_b"], hedge), ASOF)
    assert fit.mean_reverting
    assert fit.half_life is not None
    assert abs(fit.half_life / half_life - 1.0) < HALF_LIFE_TOL

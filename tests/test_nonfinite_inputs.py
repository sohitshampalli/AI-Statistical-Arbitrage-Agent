"""Infinity in the input, checked through every estimator.

rows_before rejects infinity in the rows strictly before asof, the same way it
rejects NaN, so each estimator gets the check without its own copy. Infinity at
or after asof is never read, so it must not change any result.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
import pytest

from statarb_agent.data.synthetic import simulate_cointegrated_pair
from statarb_agent.stats.cointegration import engle_granger
from statarb_agent.stats.hedge_ratio import ols_hedge_ratio
from statarb_agent.stats.mean_reversion import fit_ar1
from statarb_agent.stats.unit_root import adf_test

SEED = 7
N_OBS = 300
CUT = 200  # asof is the date of this row
ROWS_BEFORE = [0, 100, CUT - 1]  # CUT - 1 is the last row before asof
ROWS_AT_OR_AFTER = [CUT, 250]  # CUT is the asof row itself


@pytest.fixture(scope="module")
def pair() -> pd.DataFrame:
    return simulate_cointegrated_pair(seed=SEED, n_obs=N_OBS)


def _one_leg(fn: Callable) -> Callable:
    return lambda a, b, asof: fn(a, asof)


ESTIMATORS: dict[str, tuple[Callable, bool]] = {
    # name: (call taking (log_a, log_b, asof), whether log_b is read)
    "adf_test": (_one_leg(adf_test), False),
    "fit_ar1": (_one_leg(fit_ar1), False),
    "ols_hedge_ratio": (ols_hedge_ratio, True),
    "engle_granger": (engle_granger, True),
}

CASES = [
    (name, leg)
    for name, (_, two_legs) in ESTIMATORS.items()
    for leg in (("log_a", "log_b") if two_legs else ("log_a",))
]


def _with_value(pair: pd.DataFrame, leg: str, row: int, value: float) -> pd.DataFrame:
    df = pair.copy()
    df.iloc[row, df.columns.get_loc(leg)] = value
    return df


@pytest.mark.parametrize("value", [np.inf, -np.inf])
@pytest.mark.parametrize("row", ROWS_BEFORE)
@pytest.mark.parametrize(("name", "leg"), CASES)
def test_infinity_before_asof_raises(
    pair: pd.DataFrame, name: str, leg: str, row: int, value: float
) -> None:
    call, _ = ESTIMATORS[name]
    df = _with_value(pair, leg, row, value)
    with pytest.raises(ValueError, match="infinity"):
        call(df["log_a"], df["log_b"], pair.index[CUT])


@pytest.mark.parametrize("value", [np.inf, -np.inf])
@pytest.mark.parametrize("row", ROWS_AT_OR_AFTER)
@pytest.mark.parametrize(("name", "leg"), CASES)
def test_infinity_at_or_after_asof_does_not_change_result(
    pair: pd.DataFrame, name: str, leg: str, row: int, value: float
) -> None:
    call, _ = ESTIMATORS[name]
    asof = pair.index[CUT]
    before = call(pair["log_a"], pair["log_b"], asof)
    df = _with_value(pair, leg, row, value)
    assert call(df["log_a"], df["log_b"], asof) == before

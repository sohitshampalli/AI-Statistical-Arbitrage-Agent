"""Measure the pair screen at the formation length on simulated data.

This is the measurement that configs/screen.yaml cites. It uses no real data.

- T = 2013 rows, the planned number of trading days in 2010 to 2017.
- Seeds 6000 to 6999, which no test uses; 1000 simulations per row.
- Random walks: two independent driftless walks in logs, daily sd 0.015.
- Cointegrated pairs: data.synthetic.simulate_cointegrated_pair with its
  defaults and the true half-life varied.
- Every statistic comes from stats.pair.pair_stats and every decision from
  screen.apply_screen with configs/screen.yaml, the same code the CLI uses.

Run (about 4 minutes on 8 cores):

    uv run python scripts/measure_formation_screen.py
"""

from __future__ import annotations

import math
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from statarb_agent.data.synthetic import simulate_cointegrated_pair
from statarb_agent.screen import apply_screen, load_screen
from statarb_agent.stats.pair import pair_stats

T = 2013
SEEDS = range(6000, 7000)
ASOF = "2100-01-01"
HALF_LIVES = (5.0, 10.0, 20.0, 32.0, 63.0, 100.0)
SCREEN = load_screen(Path(__file__).resolve().parents[1] / "configs" / "screen.yaml")


def independent_walks(seed: int, n_obs: int = T, sigma: float = 0.015) -> pd.DataFrame:
    """Two independent driftless random walks in logs, starting at log(100)."""
    rng = np.random.default_rng(seed)
    steps = sigma * rng.standard_normal((2, n_obs - 1))
    walks = math.log(100.0) + np.concatenate(
        [np.zeros((2, 1)), np.cumsum(steps, axis=1)], axis=1
    )
    idx = pd.bdate_range("2000-01-03", periods=n_obs, name="date")
    return pd.DataFrame({"log_a": walks[0], "log_b": walks[1]}, index=idx)


def one(job: tuple[str, float, int]) -> dict[str, object]:
    kind, half_life, seed = job
    if kind == "rw":
        df = independent_walks(seed)
    else:
        df = simulate_cointegrated_pair(seed=seed, half_life=half_life, n_obs=T)
    stats = pair_stats(df["log_a"], df["log_b"], ASOF)
    result = apply_screen(stats, SCREEN)
    by_name = {c.name: c.passed for c in result.criteria}
    fit = stats.spread_ar1
    return {
        "kind": kind,
        "half_life": half_life,
        "est_half_life": fit.half_life if fit.mean_reverting else float("nan"),
        "eg_either": min(
            stats.engle_granger.a_on_b.pvalue, stats.engle_granger.b_on_a.pvalue
        ) < SCREEN.eg_pvalue_max,
        "passed": result.passed,
        **by_name,
    }


def main() -> None:
    jobs = [("rw", float("nan"), s) for s in SEEDS]
    jobs += [("coint", h, s) for h in HALF_LIVES for s in SEEDS]
    with Pool() as pool:
        rows = pd.DataFrame(pool.map(one, jobs, chunksize=20))
    for (kind, half_life), g in rows.groupby(["kind", "half_life"], dropna=False,
                                             sort=False):
        label = "random walks" if kind == "rw" else f"cointegrated, half-life {half_life:g}"
        hl = g["est_half_life"].dropna()
        p5, p50, p95 = np.percentile(hl, [5, 50, 95])
        print(
            f"{label}: n {len(g)}; EG both {g['eg_both_directions'].mean():.1%}, "
            f"either {g['eg_either'].mean():.1%}; half-life in range "
            f"{g['half_life_in_range'].mean():.1%}; legs not stationary "
            f"{g['legs_not_stationary'].mean():.1%}; full screen "
            f"{int(g['passed'].sum())} of {len(g)}; EG both but half-life out of "
            f"range {int((g['eg_both_directions'] & ~g['half_life_in_range']).sum())}; "
            f"estimated half-life p5 {p5:.2f}, median {p50:.2f}, p95 {p95:.2f}, "
            f"undefined {int(g['est_half_life'].isna().sum())}"
        )


if __name__ == "__main__":
    main()

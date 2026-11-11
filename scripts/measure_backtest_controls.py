"""Measure the backtest settings on simulated data only.

configs/backtest.yaml cites this script. It uses no real data. Calibration
seeds are 20000 to 20199; the slow tests and the control batches use other
seeds.

Part 1, time stop. For a stationary AR(1) z-score with a known half-life, apply
the z-score rule with no time stop and no window ends, and measure how long
trades last from the entry decision to the exit decision.

Part 2, edge. Run the walk-forward backtest with the settings in
configs/backtest.yaml on:
- simulated cointegrated pairs at several true half-lives (an edge is expected),
- pairs of independent random walks (no edge),
- shuffled-date placebos of one simulated cointegrated pair, both legs
  shuffled (no edge),
- simulated three-asset baskets, with and without a cointegrating relation.

Run (a few minutes on 8 cores):

    uv run python scripts/measure_backtest_controls.py
"""

from __future__ import annotations

import dataclasses
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from statarb_agent.backtest.config import BacktestConfig, load_backtest_config
from statarb_agent.backtest.controls import (
    shuffle_pair,
    simulated_pair_frames,
    summarise_batch,
)
from statarb_agent.backtest.engine import run_basket_backtest, run_pair_backtest
from statarb_agent.backtest.summary import span_metrics
from statarb_agent.data.synthetic import (
    ar1_coefficient_from_half_life,
    as_price_frame,
    simulate_basket,
)
from statarb_agent.signals.zscore import SignalParams, decide_positions

ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_backtest_config(ROOT / "configs" / "backtest.yaml")
SEEDS = range(20000, 20200)
HALF_LIVES = (5.0, 10.0, 20.0, 32.0)
START = "2010-01-01"
ASOF = "2100-01-01"


def holding_times(job: tuple[float, int]) -> list[tuple[int, str]]:
    """Trade lengths under the rule with no time stop, on a true AR(1) z-score."""
    half_life, seed = job
    n = CONFIG.controls.n_obs
    phi = ar1_coefficient_from_half_life(half_life)
    e = np.random.default_rng(seed).standard_normal(n)
    z = np.empty(n)
    z[0] = e[0]
    scale = np.sqrt(1.0 - phi * phi)
    for t in range(1, n):
        z[t] = phi * z[t - 1] + scale * e[t]
    params = SignalParams(
        entry_z=CONFIG.signal.entry_z, exit_z=CONFIG.signal.exit_z,
        stop_z=CONFIG.signal.stop_z, time_stop_bars=10**9,
    )
    out = decide_positions(z, np.ones(n, bool), np.zeros(n, bool), params)
    lengths: list[tuple[int, str]] = []
    entry = None
    for t, reason in enumerate(out.reason):
        if reason.startswith("entry"):
            entry = t
        elif reason and entry is not None:
            lengths.append((t - entry, reason))
            entry = None
    return lengths


def config_with_half_life(half_life: float) -> BacktestConfig:
    return dataclasses.replace(
        CONFIG, controls=dataclasses.replace(CONFIG.controls, half_life=half_life)
    )


def one_backtest(job: tuple[str, float, str, float, int]) -> dict[str, object]:
    kind, half_life, hedge, cost_bps, seed = job
    config = config_with_half_life(half_life)
    if kind.startswith("basket"):
        c = config.controls
        frame = simulate_basket(
            seed=seed, cointegrated=kind == "basket_cointegrated",
            half_life=c.half_life, spread_sd=c.spread_sd, sigma=c.sigma,
            n_obs=c.n_obs, start=START,
        )
        result = run_basket_backtest(
            {name: as_price_frame(frame[name]) for name in frame.columns},
            asof=ASOF, config=config, cost_bps=cost_bps,
        )
    else:
        if kind == "placebo":
            a, b = simulated_pair_frames("cointegrated", SEEDS[0], config, START)
            a, b = shuffle_pair(a, b, seed)
        else:
            a, b = simulated_pair_frames(kind, seed, config, START)
        result = run_pair_backtest(
            a, b, asof=ASOF, config=config, hedge=hedge, cost_bps=cost_bps
        )
    metrics = span_metrics(result)
    closed = result.trades.loc[~result.trades["open"]]
    return {
        "kind": kind, "half_life": half_life, "hedge": hedge, "cost_bps": cost_bps,
        "seed": seed,
        "sharpe": metrics["sharpe"],
        "gross_sharpe": metrics["gross_sharpe"],
        "total_return": metrics["total_return"],
        "gross_return": metrics["price_return"] + metrics["distribution_return"],
        "n_trades": metrics["n_trades"],
        "hit_rate": metrics["hit_rate"],
        "share_in_market": metrics["share_in_market"],
        "time_stops": int((closed["exit_reason"] == "time_stop").sum()),
        "stops": int((closed["exit_reason"] == "stop").sum()),
        "window_ends": int((closed["exit_reason"] == "window_end").sum()),
        "holding": float(closed["bars_held"].mean()) if len(closed) else float("nan"),
    }


def main() -> None:
    years = (CONFIG.controls.n_obs - CONFIG.formation_days) / 252
    with Pool() as pool:
        print(f"Part 1. Trade length with no time stop, {len(SEEDS)} seeds of "
              f"{CONFIG.controls.n_obs} rows per half-life")
        jobs = [(h, s) for h in HALF_LIVES for s in SEEDS]
        results = pool.map(holding_times, jobs, chunksize=20)
        for h in HALF_LIVES:
            pairs = [p for (hh, _), r in zip(jobs, results, strict=True) if hh == h for p in r]
            lengths = np.array([p[0] for p in pairs])
            stops = np.mean([p[1] == "stop" for p in pairs])
            q = np.percentile(lengths, [50, 75, 90, 95])
            print(
                f"  half-life {h:g}: {len(lengths)} trades; length median {q[0]:.0f}, "
                f"p75 {q[1]:.0f}, p90 {q[2]:.0f}, p95 {q[3]:.0f}; within "
                f"{CONFIG.signal.time_stop_bars} bars {np.mean(lengths <= CONFIG.signal.time_stop_bars):.1%}; "
                f"mean {lengths.mean():.1f}; stopped out {stops:.1%}"
            )

        print(f"\nPart 2. Walk-forward backtests, {len(SEEDS)} seeds each, "
              f"{years:.1f} years of trading per seed")
        jobs2 = [
            ("cointegrated", h, hedge, CONFIG.cost_bps_per_leg, s)
            for h in HALF_LIVES for hedge in CONFIG.hedge_variants for s in SEEDS
        ]
        jobs2 += [
            ("cointegrated", 10.0, "static", c, s) for c in (0.0, 20.0) for s in SEEDS
        ]
        jobs2 += [
            ("random_walk", 10.0, hedge, c, s)
            for hedge in CONFIG.hedge_variants for c in (0.0, CONFIG.cost_bps_per_leg)
            for s in SEEDS
        ]
        jobs2 += [
            ("placebo", 10.0, "static", c, s)
            for c in (0.0, CONFIG.cost_bps_per_leg) for s in SEEDS
        ]
        jobs2 += [
            (kind, 10.0, "johansen", c, s)
            for kind in ("basket_cointegrated", "basket_independent")
            for c in (0.0, CONFIG.cost_bps_per_leg) for s in SEEDS
        ]
        rows = pd.DataFrame(pool.map(one_backtest, jobs2, chunksize=10))
    keys = ["kind", "half_life", "hedge", "cost_bps"]
    for key, g in rows.groupby(keys, sort=False):
        s = summarise_batch(g)
        trades = g["n_trades"].sum()
        print(
            f"  {key[0]}, half-life {key[1]:g}, {key[2]}, {key[3]:g} bps: mean Sharpe "
            f"{s['mean_sharpe']:.2f} (p05 {s['sharpe_p05']:.2f}, median "
            f"{s['median_sharpe']:.2f}, p95 {s['sharpe_p95']:.2f}); net return per year "
            f"{s['mean_total_return'] / years:.2%}; gross per year "
            f"{s['mean_gross_return'] / years:.2%} (t {s['gross_return_t']:.1f}); "
            f"positive {s['share_positive']:.1%}; Sharpe > 1 "
            f"{s['share_sharpe_above_1']:.1%}; trades per year "
            f"{s['mean_trades'] / years:.1f}; exits by time stop "
            f"{g['time_stops'].sum() / trades:.1%}, stop {g['stops'].sum() / trades:.1%}, "
            f"window end {g['window_ends'].sum() / trades:.1%}; mean holding "
            f"{g['holding'].mean():.1f} bars; in market {g['share_in_market'].mean():.1%}"
        )


if __name__ == "__main__":
    main()

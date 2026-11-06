# Status

Phase tracker. Update this file in the same commit as the work it describes.
Gates are defined in docs/PROJECT_BRIEF.md.

## Current phase: 1. Foundations

Gate: code recovers true beta and half-life on synthetic data. Not yet passed.

| Step | Commit | Status |
|---|---|---|
| 1. Synthetic pair simulator (data/synthetic.py) and tests | 1 | done |
| 2. As-of helper and ADF wrapper (stats/unit_root.py) | 2 | done |
| 3. OLS hedge ratio and Engle-Granger, both directions | 3 | done |
| 4. AR(1) fit, OU parameters and half-life | 4 | not started |
| 5. Hypothesis property test across seeds | 5 | not started |

## Later phases

| Phase | Status |
|---|---|
| 2. Real pairs | not started |
| 3. Backtester | not started |
| 4. Agent | not started |
| 4b. Dashboard | not started |
| 5. Experiment | not started |
| 6. Paper trading, README, paper | not started |

## Notes

- statsmodels 0.15.0: call `adfuller(..., result_object=True)`; the tuple default is
  deprecated and raises FutureWarning (pytest treats FutureWarning as an error).
- statsmodels 0.15.0: `coint` returns a `CointResult` regardless of `return_results`;
  use its attributes `coint_t`, `pvalue`, `critical_values`.
- pandas 3.1.1: `bdate_range` produces `datetime64[us]`, not ns.
- ADF on a pure random walk at n = 2520 rejected 6.3 to 6.7 percent of the time at
  a nominal 5 percent over 1000 seeds (0 to 999). A single fixed-seed levels test is
  a lottery (seed 7 rejected at p = 0.0085), so levels behaviour is tested by
  rejection rate across seeds 1000 to 1499 in a slow test.
- Slow tests are skipped by default (`addopts = -m "not slow"`); run them with
  `uv run pytest -q -m slow`.
- `rows_before` clears the index `freq`. pandas derives `freq` from the whole index,
  so a row at or after asof could change metadata on the rows before it. Estimator
  results were not affected, because they read values only, but no part of the
  output should depend on future rows.
- Engle-Granger power at T = 2520, default parameters, seeds 0 to 999: worst p-value
  2.93e-6 for B on A and 2.92e-6 for A on B. B on A is not weaker, so power is
  tested on one fixed seed at p < 0.01 in both directions.
- Engle-Granger size at a nominal 5 percent on independent random walks, seeds 2000
  to 2499: x on y 5.6 percent, y on x 7.6 percent, both inside the bounds of 1.5 to
  10 percent. The y on x rate compares with 4.8 percent on the calibration seeds
  (0 to 999), about 2 standard errors apart.
- The rate at which either direction rejected was 8.7 percent on the calibration
  seeds and 10.2 percent on the test seeds, so both directions are always reported
  separately and never combined by taking the smaller p-value.

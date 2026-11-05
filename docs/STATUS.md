# Status

Phase tracker. Update this file in the same commit as the work it describes.
Gates are defined in docs/PROJECT_BRIEF.md.

## Current phase: 1. Foundations

Gate: code recovers true beta and half-life on synthetic data. Not yet passed.

| Step | Commit | Status |
|---|---|---|
| 1. Synthetic pair simulator (data/synthetic.py) and tests | 1 | done |
| 2. As-of helper and ADF wrapper (stats/unit_root.py) | 2 | not started |
| 3. OLS hedge ratio and Engle-Granger, both directions | 3 | not started |
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

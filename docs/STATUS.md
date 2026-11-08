# Status

Phase tracker. Update this file in the same commit as the work it describes.
Gates are defined in docs/PROJECT_BRIEF.md.

## Current phase: 1. Foundations (gate passed, Phase 2 not started)

Gate: code recovers true beta and half-life on synthetic data. Passed 2026-11-06.

| Step | Commit | Status |
|---|---|---|
| 1. Synthetic pair simulator (data/synthetic.py) and tests | 1 | done |
| 2. As-of helper and ADF wrapper (stats/unit_root.py) | 2 | done |
| 3. OLS hedge ratio and Engle-Granger, both directions | 3 | done |
| 4. AR(1) fit, OU parameters and half-life | 4 | done |
| 5. Hypothesis property test across seeds | 5 | done |

## Phase 1 gate evidence

All Phase 1 tests pass: `uv run pytest -q` and `uv run pytest -q -m slow`.

Beta recovery:
- `tests/test_hedge_ratio.py::test_beta_recovery`: error under 0.05 at T = 2520.
- `tests/test_hedge_ratio.py::test_exact_recovery_without_spread`: exact with no spread.
- `tests/test_properties.py::test_recovers_truth_across_seeds_and_parameters`: error
  under 0.03 at T = 10,000, for beta in [0.5, 2] and half-life in [5, 15].

Half-life recovery:
- `tests/test_mean_reversion.py::test_half_life_strict_at_long_length`: relative error
  under 0.20 at T = 10,000.
- `tests/test_mean_reversion.py::test_half_life_loose_at_realistic_length`: relative
  error under 0.35 at T = 2520.
- `tests/test_mean_reversion.py::test_noiseless_ar1_is_recovered_exactly`: exact.
- `tests/test_mean_reversion.py::test_recovers_phi_on_true_spread`: phi within 4
  standard errors.
- The same property test: relative error under 0.25 at T = 10,000.

Look-ahead tests, each changing rows at or after asof:
- `rows_before` and `paired_rows_before`: `tests/test_asof.py`.
- `adf_test`: `tests/test_unit_root.py`.
- `ols_hedge_ratio`: `tests/test_hedge_ratio.py`.
- `engle_granger`: `tests/test_cointegration.py`.
- `fit_ar1`: `tests/test_mean_reversion.py`.
- `spread` has no asof because it estimates nothing;
  `test_spread_row_t_depends_only_on_row_t` shows row t uses only row t.
- `_ou_parameters` reads no data. The simulator generates data and reads none.

This gate is an in-sample result on synthetic data. It says nothing about real pairs.

## Open decisions

- Phase 2 or 3: the AR(1) half-life is badly biased at T = 252, the formation window.
  Median estimate on the true spread (seeds 5000 to 5999): 8.44 at true half-life 10,
  19.37 at 32, 25.94 at 60. A time stop of about 3 estimated half-lives would fire too
  early. Options: a fixed time stop in configs, a longer OU window, or half-life as a
  diagnostic only.

## Later phases

| Phase | Status |
|---|---|
| 2. Real pairs | not started |
| 3. Backtester | not started |
| 3b. Universe strategy | not started |
| 4. Agent | not started |
| 4b. Dashboard | not started |
| 5. Experiment | not started |
| 6. Paper trading, README, paper | not started |

## Notes

- cvxpy is a Phase 3b dependency (portfolio construction). It is not installed;
  add it when Phase 3b starts.
- statsmodels 0.15.0: call `adfuller(..., result_object=True)`; the tuple default is
  deprecated and raises FutureWarning (pytest treats FutureWarning as an error).
- statsmodels 0.15.0: `coint` returns a `CointResult` regardless of `return_results`;
  use its attributes `coint_t`, `pvalue`, `critical_values`.
- pandas 3.1.1: `bdate_range` produces `datetime64[us]`, not ns.
- ADF on a pure random walk at n = 2520 rejected 6.3 to 6.7 percent of the time at
  a nominal 5 percent over 1000 seeds (0 to 999). A single fixed-seed levels test is
  a lottery (seed 7 rejected at p = 0.0085), so levels behaviour is tested by
  rejection rate across seeds 1000 to 1499 in a slow test.
- Property test: 25 derandomized examples, about 14 s, marked slow. Over 500 measured
  draws of its strategy no bound was reached; the closest was half-life relative
  error 0.2000 against 0.25.
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
- AR(1) half-life has a downward small-sample bias, documented and not corrected.
  In-sample pipeline, true half-life 10: mean relative error -3.3 percent at
  T = 2520 (400 seeds, worst +30.85 percent at seed 118) and -0.7 percent at
  T = 10,000 (200 seeds, worst +15.37 percent at seed 111).
- 0 < b < 1 is necessary but not sufficient for mean reversion. Random walks at
  T = 2520 satisfied it on 951 of 1000 seeds (seeds 5000 to 5999, 95.1 percent) and
  on 959 of 1000 seeds (seeds 0 to 999, 95.9 percent), because the bias pulls b
  under 1. `mean_reverting=True` only means the OU formulas can be
  computed. The screening decision belongs to the cointegration tests plus a
  half-life range, to be decided in Phase 2.
- `_ou_parameters` returns mean_reverting=False for a non-finite b. Before this, a
  NaN b failed both comparisons and returned True with NaN parameters. `fit_ar1`
  raises ValueError on infinity before asof. Before this, infinity in the last row
  before asof returned a fit with b = +/-inf, and in an earlier row it raised a
  statsmodels or numpy error instead of ValueError.
- Implied half-life on those random walks at T = 2520: median 368.92, 5th percentile
  119.76, minimum 64.33; under 100 bars on 2.1 percent of seeds and under 50 bars on
  none. True spread at half-life 10: median 9.88, maximum 13.90.
- That gap exists only because the true half-life is 10 and T is long, so a
  half-life cap cannot replace the cointegration test. At T = 2520 the true spread
  reached 51.01 at half-life 30 and 54.71 at half-life 32, below the random-walk
  minimum of 64.33 on these seeds but touching the 51.0 seen on seeds 0 to 999; at
  half-life 60, 25.8 percent of fits exceeded 64.33. At T = 252, the formation
  window, the groups overlap heavily: random-walk median 38.41, 59.9 percent of seeds
  under 50 bars, while true half-life 32 gives a median of 19.37. KO/PEP half-life:
  Graziano (2026), arXiv 2609.35359, section 2.2, in-sample estimate, about 31.9
  trading days.

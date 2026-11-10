# Status

Phase tracker. Update this file in the same commit as the work it describes.
Gates are defined in docs/PROJECT_BRIEF.md.

## Current phase: 2. Real pairs (in progress)

Gate: all estimates use only data before their as-of date.

| Step | Commit | Status |
|---|---|---|
| 1. Study config, test-period lock, network guard for tests | 1 | done |
| 2. Source interface, snapshot store and manifest | 2 | done |
| 3. yfinance price source and total-return index | 3 | done, live check passed |
| 4. Calendar alignment and data checks | 4 | done |
| 5. Screen config, pair statistics and trial log | 5 | done |
| 6. CLI: `statarb analyse`, `fetch`, `demo` | 6 | done |
| 7. Live download and demo run (needs approval) | 7 | not started |

Decisions for Phase 2 (2026-11-08):
- Manifest at `data/manifest.json`, committed; `.gitignore` becomes `/data/*` plus
  `!/data/manifest.json`. Trial log at `trials/trials.jsonl`, committed.
- SPY, from its own snapshot, is the reference trading calendar.
- Demo pairs are labelled `case_study`, user-chosen pairs `exploratory`, V vs XOM
  `control`, the simulated pair `synthetic`.
- `analyse` downloads an uncached ticker and says so, naming the snapshot used;
  `--offline` forbids downloads. Formation period only; the CLI refuses the
  validation period until Phase 3.
- Screen (fixed 2026-11-10, `configs/screen.yaml`, before any real pair was run):
  Engle-Granger p < 0.05 in both directions, half-life in [1, 63] bars on the full
  formation window, both legs fail to reject ADF on levels at 5 percent. The 5
  percent levels are conventional; the half-life floor of 1 bar follows from
  next-bar execution and the cap of 63 bars is one walk-forward trading window.
  The measurement behind it is in the Notes ("Screen at the formation length").
- Download start 2010-01-01. yfinance with repair=False; anomalies are flagged,
  never fixed: absolute daily log return above 0.4, a dividend above 10 percent of
  the close, runs of 5 or more identical closes.
- Tickers are sanitised before any file path is built (uppercase letters, digits,
  . and -, normalised to Yahoo's - form). Snapshots store a file hash and a content
  hash, and both are verified on read.
- Ask before the commit 3 network test and before the commit 7 live run.

## Phase 1: Foundations (gate passed 2026-11-06)

Gate: code recovers true beta and half-life on synthetic data.

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

- Phase 3: a one-shot final-test command. The test period may be used once; how
  that single run is triggered, logged and protected from repeats is decided in
  Phase 3. Every unlock event and every test-period run will be recorded in the
  trial log.
- Phase 6: live paper trading needs a separate code path that the research lock
  does not apply to, because it works on today's data. To be designed later; it
  must not weaken the research lock.

## Later phases

| Phase | Status |
|---|---|
| 2. Real pairs | in progress |
| 3. Backtester | not started |
| 3b. Universe strategy | not started |
| 4. Agent | not started |
| 4b. Dashboard | not started |
| 5. Experiment | not started |
| 6. Paper trading, README, paper | not started |

## Notes

- Test-period lock (`statarb_agent.study`): TEST_START = 2022-01-01 is a code
  constant; `configs/study.yaml` cannot move it. Unlocked only when all hold: the
  StudyConfig in use sets the flag; `configs/study.yaml` is in HEAD with no staged
  or unstaged changes and sets `test_period_unlocked: true`; PREREGISTRATION.md is
  in HEAD with no staged or unstaged changes. Both files use the same check
  (`committed_clean_commit`), so a flag set on disk but not committed keeps the
  lock. `unlock_evidence` returns the commit hashes of both files; every unlock
  event in the trial log (commit 5) records them. Locked,
  `require_before_test_period` refuses any asof after 2022-01-01 (exactly 2022-01-01
  is allowed, since it reads rows up to 2021-12-31), `clip_end_to_open_period` stops
  downloads at 2022-01-01, and `drop_locked_rows` removes test-period rows from data
  that already has them. It protects library paths only, not a notebook that reads
  Parquet directly. It is not in `rows_before`, because synthetic tests use dates
  up to about 2038.
- The validation period (2018 to 2021) is blocked only in the CLI until Phase 3,
  not in the library: `load` and the estimators accept any asof up to
  TEST_START. The library lock covers the test period only.
- Tests cannot reach the network: an autouse fixture in `tests/conftest.py` blocks
  sockets, DNS, and the curl_cffi and requests sessions unless a test is marked
  `network` (deselected by default). curl_cffi needs its own patch because it uses
  libcurl, not Python sockets, and yfinance uses it.
- Snapshot store (`sources/base.py`): files at `data/raw/<source>/<key>/<UTC
  timestamp>.parquet`, opened in exclusive mode so a snapshot is never overwritten.
  The manifest (`data/manifest.json`) is rewritten through a temporary file and
  os.replace, so an interrupted write keeps the old one. Every read checks the
  path stays inside `data/raw/`, then the file SHA-256, then the content SHA-256
  (column names, dtypes, index name and `pd.util.hash_pandas_object`, because that
  function alone ignores column names). The content hash can change across pandas
  versions, so each entry records pandas_version. The store has no asof: it returns
  whole snapshots, and each source's `load` applies asof.
- Tickers pass `normalise_ticker` before any path or request. Any non-ASCII
  character is rejected first, because str.upper maps some look-alikes to ASCII
  (dotless i to I, long s to S). The input is then uppercased and must be ASCII
  letters and digits joined by single "." or "-", at most 12 characters; "." is
  rewritten to "-" (brk.b becomes BRK-B). The store accepts only keys already in
  normalised form, so no key can hold a separator or "..".
- Price source (`sources/prices.py`): stores Yahoo's frame as delivered by
  `Ticker.history(auto_adjust=False, back_adjust=False, actions=True, repair=False,
  keepna=False, rounding=False, prepost=False, interval="1d")`, except that dtypes
  are converted to Parquet-safe ones (float64, int64 volume, microsecond index) when
  no value changes; each conversion is written to the manifest notes. Signals use
  `tr_close`, a forward-accumulated total-return index from Close, Dividends and
  Capital Gains: row t uses only rows up to t, so a later dividend never revises it.
  `load` cuts at asof before any value check or computation, and does not return
  Yahoo's Adj Close (it embeds later dividends). A split after asof rescales every
  earlier row of Yahoo's split-adjusted Close by one factor, a constant shift in
  logs: the intercept moves, the hedge ratio and tests do not.
- Live check, 2026-11-08, first approved KO download (2010-01-01 to 2022-01-01):
  the download succeeded but the store refused to save it, because the content
  hash changed across the Parquet write and read. Fixes: the store's error names
  each dtype, column or row change, and fetch converts to Parquet-safe types first.
- Live check, 2026-11-08, second approved KO download, same limits, passed.
  Confirmed cause of the first failure: yfinance 1.8.0 returns the index as
  `datetime64[s, America/New_York]` (unit s), which Parquet reads back as ms. The
  earlier guess that pandas 3.1.1 gives [us] for yfinance's conversion was wrong.
  All columns arrived in their target types (float64, Volume int64), so the only
  conversion note was "index converted from datetime64[s, America/New_York] to
  microsecond unit". Results, from 3021 rows, 2010-01-04 to 2021-12-31, no warnings:
  - Split read from the Splits column: 2012-08-13, ratio 2. Close return that day
    -0.2412 percent, tr_close return -0.2412 percent, so Close is split-adjusted
    (asserted: below 10 percent).
  - 48 payments, maximum 0.9003 percent of the previous close; 10 before the
    split (max 0.8389 percent), 38 after (max 0.9003 percent). Dividends are on
    the same split basis as Close (asserted: below 5 percent on both sides).
  - tr_close vs Yahoo's Adj Close (reported, not asserted): maximum absolute
    daily log-return difference 3.084e-04, on 2020-03-13; range of
    log(tr_close / adj_close) over the period 6.127e-04.
  The data was in a temporary folder and was not kept. The network test prints
  the raw frame's column dtypes and index dtype, unit and tz (no values) before
  any conversion.
- Alignment (`data/alignment.py`): `align_pair` compares both series in
  [start, asof) and by default refuses any date present in one only, listing the
  dates. Dropping is allowed only up to `max_unmatched_days`, and every dropped
  date is in the report. Nothing is joined or filled silently.
- Data checks (`data/checks.py`), on rows in [start, asof) only, against SPY's
  trading days. Fatal: enough_history, listed_throughout, no_missing_days,
  no_extra_days. Flags, never fatal and never fixed: large_move (absolute daily
  log return of close above 0.4), large_distribution (dividend plus capital gain
  above 10 percent of the previous close), stale_closes (5 or more identical
  consecutive closes). Flags go into the trial log (commit 5) and CLI output
  (commit 6).
- Screen at the formation length (T = 2013 rows, seeds 6000 to 6999, 1000
  simulations per row, `scripts/measure_formation_screen.py`, run through
  `pair_stats` and `apply_screen`). Full screen passes: independent random walks
  10 of 1000; cointegrated pairs with true half-life 5, 10, 20, 32, 63, 100:
  927, 932, 938, 938, 684, 358 of 1000. On random walks, Engle-Granger rejected
  in both directions on 1.4 percent and in either on 8.5 percent, so requiring
  both does the filtering. The half-life window removed no random walk that had
  passed Engle-Granger; it removed 24 true pairs at half-life 63 and 11 at 100.
  The ADF criterion on the legs costs 6 to 7 percent of true pairs at every
  half-life. Estimated half-life medians: random walks 175.85 (12 undefined);
  true 10: 9.62; true 32: 28.35; true 63: 49.90. T = 2013 is the planned count of
  trading days in 2010 to 2017; it is confirmed against SPY's snapshot when that
  is downloaded. A slow test on other seeds (7000 onward) measured 4 of 300
  random walks and 188 of 200 true pairs passing, inside its bounds of at most 4
  percent and at least 85 percent.
- `pair_stats` (`stats/pair.py`) gathers ADF on levels and returns, the OLS
  hedge ratio, Engle-Granger in both directions and the AR(1) fit of the
  in-sample spread, on rows in [start, asof). `apply_screen` (`screen.py`) only
  compares those numbers with the config.
- Trial log (`trials.py`, file `trials/trials.jsonl`, committed): one JSON line
  per analysis or evaluated backtest configuration, appended with a single
  O_APPEND write and never rewritten. Each line has the label, tickers, period,
  data source, survivorship flag, snapshot ids, config hashes, code commit and
  dirty flag, whether the test period was touched, the unlock commits if any, the
  outcome (ok, refused, error) with its reason, and results. Non-finite numbers
  are stored as null. A damaged log (bad JSON, unknown keys, missing final
  newline) stops both reads and writes. `record_unlock_event` writes one
  `unlock_event` line per distinct pair of unlock commits; a trial that touched
  the test period cannot be built without them.
- Analysis path (`analysis.py`, class `Analyser`) and CLI (`cli.py`, script
  `statarb`): `statarb fetch TICKER...` (skips cached tickers unless `--refresh`),
  `statarb analyse A B [--offline] [--json]`, `statarb demo`. A real pair is
  cached if needed, loaded with the period's asof, checked against SPY's trading
  days, aligned, analysed on log `tr_close` and screened; one trial line is
  written whatever the outcome. A refusal (failed data check, date mismatch, no
  data) is a normal logged result with exit code 2. Invalid input (bad ticker,
  the same ticker twice) raises and logs nothing. Thresholds are in
  `configs/data.yaml`, demo pairs in `configs/pairs.yaml`, each with its reasons.
  If the manifest lists a snapshot whose file is missing (a fresh clone),
  `analyse` downloads a new snapshot and says so; with `--offline` it stops and
  names the `statarb fetch` command.
- Phase 2 gate test: `tests/test_analysis_cli.py::
  test_cli_analyse_ignores_cached_rows_at_or_after_asof` replaces every snapshot
  (both legs and the calendar) with one that differs from the as-of date on
  (prices, payouts, a split, NaN, missing days) and requires identical output;
  `test_the_look_ahead_test_can_fail` shows the same change one row earlier is
  detected.
- The synthetic demo pair uses seed 20261110, fixed before it was simulated.
- A fresh clone has manifest entries but no snapshot files. Reading one raises
  SnapshotMissingError naming the ticker and snapshot id and telling the user to
  run `statarb fetch`. README (commit 7) must say that a fresh download creates
  new snapshots, so numbers can differ slightly, and that every result records
  its snapshot ids.
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
- The infinity check now lives in `rows_before`, next to the NaN check, so every
  estimator gets it and `fit_ar1` no longer has its own copy. Before this,
  `ols_hedge_ratio` returned alpha = beta = inf when log_a contained infinity, and
  `adf_test` and `engle_granger` raised statsmodels `MissingDataError` instead of
  ValueError. Only the selected rows are checked, so infinity at or after asof
  changes nothing; `tests/test_nonfinite_inputs.py` tests both through all four
  estimators. Non-numeric DataFrame columns are not checked for infinity.
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

# statarb-agent

An open research project on one question: do cointegration-based pairs among US
large caps still mean-revert after realistic costs, and can a Claude agent that
reads only point-in-time news filter out structural breaks?

Rigour and honesty matter more than returns here. This is paper research only:
no live money, no live trading endpoints, and nothing in this repository is
investment advice.

## Status

Phase 3 of 6 is done: the statistics, the data layer, the command line and a
walk-forward backtester with costs, controls and a trial log are built and
tested. The dashboard and the agent are not built yet. `docs/STATUS.md` has the
current state; `docs/PROJECT_BRIEF.md` is the plan.

## Quickstart

Requirements: [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 itself).

```sh
git clone <this repository> && cd statarb-agent
uv sync
uv run pytest -q            # fast tests, no network
uv run statarb demo         # downloads the demo tickers, then analyses them
uv run statarb analyse KO PEP
```

Commands:

| Command | What it does |
|---|---|
| `uv run statarb fetch TICKER...` | Download daily prices for tickers that are not cached. `--refresh` makes a new snapshot. |
| `uv run statarb analyse A B` | Analyse any two US tickers on the formation period (2010 to 2017). Downloads what is missing unless `--offline`. `--json` prints JSON. |
| `uv run statarb demo` | Analyse every demo pair, the control pair and the synthetic pair. |
| `uv run statarb backtest A B` | Walk-forward backtest of two tickers on 2010 to 2021 (formation and validation). |
| `uv run statarb backtest-demo` | Every pre-stated backtest and control, once. Refuses to run twice. |
| `uv run statarb runs` / `summarise` | Read the stored results. Adds no trial. |

Every analysis and every backtest adds a line to the trial log, which the
Deflated Sharpe ratio counts. Read stored results with `statarb runs` instead of
running something again.

Tests: `uv run pytest -q` (fast), `uv run pytest -q -m slow` (Monte Carlo
calibration, a few minutes), `uv run ruff check` (lint).

## What an analysis does

For two tickers, on rows strictly before the as-of date of the period:

1. Data checks against SPY's trading days: enough history, listed for the whole
   window, no missing or extra days. A failed check refuses the analysis.
   Suspicious values (a daily move above 0.4 in log return, a payout above 10
   percent of the previous close, five or more identical closes) are flagged and
   never corrected.
2. Augmented Dickey-Fuller tests on each log price and each log return.
3. A static OLS hedge ratio and the Engle-Granger cointegration test in both
   directions. Both directions are always reported; the smaller p-value is never
   used alone.
4. An AR(1) fit of the spread, which gives the half-life when it exists.
5. A fixed screen (`configs/screen.yaml`): Engle-Granger p below 0.05 in both
   directions, half-life between 1 and 63 bars, both legs not stationary. The
   values were set from theory and simulation before any real pair was analysed;
   the config file records the measurement.

Prices are a total-return index built forward from close, dividends and capital
gains, so a dividend paid later never changes an earlier value.

Every analysis, including refused ones, is appended to `trials/trials.jsonl`
with its label, snapshot ids, config hashes and code commit. Pairs you choose
yourself are labelled exploratory: they are not pre-registered.

## Result so far: the famous pairs fail the formation-window screen

Formation period, 2010-01-04 to 2017-12-29, 2013 trading days, in sample, run on
2026-11-10. Engle-Granger p-values are given as "A on B / B on A".

| Pair | Label | Engle-Granger p | Half-life (bars) | Screen |
|---|---|---|---|---|
| V / MA | case study | 0.228 / 0.208 | 78.04 | fail |
| KO / PEP | case study | 0.431 / 0.633 | 159.24 | fail |
| XOM / CVX | case study | 0.442 / 0.549 | 120.34 | fail |
| HD / LOW | case study | 0.246 / 0.275 | 97.46 | fail |
| EWA / EWC | case study | 0.300 / 0.175 | 88.61 | fail |
| V / XOM | control | 0.875 / 0.466 | 277.36 | fail |
| Synthetic pair (true beta 1.5, half-life 10) | synthetic | 1.36e-14 / 1.74e-14 | 7.90 | pass |

None of the five case-study pairs shows cointegration over the full eight-year
window, and neither does the control pair. The simulated pair, which is
cointegrated by construction, passes. This is a result, not a failure of the
tool: a pair can co-move for a few years and still not be cointegrated over
eight. Whether shorter rolling windows find tradable episodes, and whether those
survive costs, is the question for the backtester phase. The numbers above are
in the trial log with their snapshot ids.

## Backtest results: no edge claimed

Run once on 2026-11-12 (`statarb backtest-demo`, commit 546443e). Settings were
fixed in `configs/backtest.yaml` from the brief, stated assumptions and simulated
data before any real-data backtest: walk-forward with a 252-day formation window
and a 63-day trading window, enter at |z| > 2, exit at |z| < 0.5, stop at |z| > 4,
time stop 30 days, dollar-neutral, 10 basis points per leg per trade (sensitivity
at 0 and 20), a 50 basis point annual borrow fee, dividends owed on the short leg.
Every number below is net of costs.

**The strategy as stated in advance takes no positions.** Its candidates were the
five case-study pairs and the KO / PEP / KDP basket in `configs/pairs.yaml`. All
six failed the formation-period screen (2010 to 2017), so none is traded and there
is no headline return.

**The engine finds an edge where one was built in, and none where none was.**
Control batches, 200 simulated pairs each, 11 years of walk-forward trading:

| Control | Hedge | Mean net Sharpe | Positive | Net Sharpe above 1 | Gross return t |
|---|---|---|---|---|---|
| Cointegrated (half-life 10) | static | 0.84 | 99.5% | 29.0% | +51.0 |
| Cointegrated | rolling | 0.85 | 100.0% | 28.5% | +55.6 |
| Cointegrated | kalman | 0.86 | 99.5% | 27.5% | +54.8 |
| Independent random walks | static | -0.06 | 41.5% | 0.0% | -0.0 |
| Independent random walks | rolling | -0.03 | 43.0% | 0.0% | +1.8 |
| Independent random walks | kalman | -0.05 | 41.0% | 0.0% | +0.5 |

**EXPLORATORY: the case-study pairs that failed the screen.** The plan said to
backtest them anyway, as case studies. These results are not the strategy and
are not evidence of an edge. Validation period 2018-01-02 to 2021-12-31 (1008
days, never used to set anything), net Sharpe ratio at 0 / 10 / 20 basis points
per leg, static hedge; Deflated Sharpe ratio at 10 basis points against all 57
real-data backtest trials; placebo rate = share of 200 shuffled-date placebos
(both legs' dates shuffled) that did at least as well on the validation period.

| Pair | Net Sharpe 0 / 10 / 20 bps | Deflated Sharpe (57 trials) | Placebo rate |
|---|---|---|---|
| V / MA | 0.81 / 0.55 / 0.29 | 0.08 | 0.100 |
| KO / PEP | 0.17 / 0.04 / -0.09 | 0.01 | 0.398 |
| XOM / CVX | 0.36 / 0.22 / 0.08 | 0.02 | 0.259 |
| HD / LOW | 0.84 / 0.73 / 0.63 | 0.11 | 0.060 |
| EWA / EWC | -0.11 / -0.34 / -0.56 | 0.00 | 0.638 |
| V / XOM (control, unrelated) | -0.65 / -0.74 / -0.82 | 0.00 | 0.896 |
| KO / PEP / KDP (Johansen basket) | -0.59 / -0.68 / -0.77 | 0.00 | not run |

The rolling and Kalman hedge variants are in `docs/STATUS.md`. The best Deflated
Sharpe ratio of all 57 runs on the validation period is 0.23. The two best pairs
here, V / MA and HD / LOW, lost money on the formation period at every cost
level, and their placebo rates (0.100 and 0.060) are not below 0.05 even before
correcting for the number of runs. The validation period has now been seen and is
not used again to choose designs.

Limitations of these numbers:
- A position still open on the last day (12 of 57 runs) is marked to market but
  has not paid its exit cost (0.098 percent of capital at 10 bps); charging it
  would lower those runs' validation Sharpe by 0.005 to 0.015.
- The basket trades the Johansen eigenvector, which is not dollar-neutral, in
  every window, although the Johansen test found no relation in 35 of its 44
  windows. One basket trade was long all three legs with no hedge.
- An entry on the day before a trading window ends is closed one day later and
  pays costs twice (6 of 576 closed trades at 10 bps).
- Trial log lines 9 to 97 record `code_dirty: true` although the code was clean:
  the dirty check counted the trial log itself. Fixed on 2026-11-23; the lines
  are kept as written.
- Free data has survivorship bias (below), and four years of validation data is a
  small sample.

## Data sources and limitations

- Prices: Yahoo Finance through the `yfinance` library (no key). The data is used
  for personal, non-commercial research only and is not redistributed: the
  downloaded files stay on the author's computer and are not in this
  repository. The dashboard runs locally and is not published; screenshots of
  its charts will be added to this README. Yahoo's Terms of Service restrict automated
  access to its services; `docs/THIRD_PARTY.md` quotes the terms and records
  this as an open question.
- Every third-party package and data source, with licences and terms, is
  listed in `docs/THIRD_PARTY.md`.
- Survivorship bias: free data covers only tickers that still trade. Companies
  that were delisted or acquired are missing, so any universe built from it
  looks better than the real past did. Every real-data result carries this flag.
- Snapshots: each download is stored as an immutable snapshot under `data/raw/`
  with a file hash and a content hash, both checked on every read.
  `data/manifest.json` (committed) lists every snapshot with its source, request,
  retrieval time and hashes.
- Back up `data/raw/` outside git (for example with Time Machine). The snapshot
  files are not in the repository, and a snapshot that is lost cannot be
  downloaded again in the same form: a new download gets a new snapshot id.
- A fresh clone has the manifest but not the snapshot files. `statarb analyse`
  and `statarb demo` download new snapshots when a file is missing. Yahoo
  occasionally revises history, so numbers from a fresh download can differ
  slightly from the ones above. Every result records the snapshot ids it used,
  so two runs can always be told apart.
- Study periods: formation 2010 to 2017, validation 2018 to 2021, test from
  2022. The test period is locked in code: nothing can read or compute on it
  until a pre-registration file and an unlock flag are both committed.
  Downloads stop at 2022-01-01 while it is locked.
- No look-ahead: every estimator takes an as-of date and reads only rows
  strictly before it. Each one has a test that changes later rows and requires
  identical output, and an end-to-end test does the same through the command
  line.
- Small samples and regime change: a pass on one window says nothing about the
  next. In-sample half-lives are biased downward in short windows.

## Layout

```
configs/          study periods, screen, data checks, demo pairs (each explains its values)
src/statarb_agent/
  stats/          ADF, Engle-Granger, Johansen, hedge ratio (OLS, rolling, Kalman), AR(1)
  signals/        the z-score trading rule
  backtest/       walk-forward engine, accounting, metrics, controls, run artifacts
  sources/        price source, snapshot store, manifest, ticker validation
  data/           synthetic pair simulator, calendar alignment, data checks
  study.py        study periods and the test-period lock
  screen.py       the pair screen
  trials.py       the append-only trial log
  analysis.py     one pair end to end
  cli.py          the statarb command
scripts/          measurements cited by the configs
tests/            fixed-seed tests; slow Monte Carlo tests are marked slow
trials/           trials.jsonl, every analysis and backtest ever run
reports/runs/     stored run artifacts (not in git; derived from downloaded prices)
docs/             brief, status, sprint plan, handoff notes
```

## References

- Engle, R. F. and Granger, C. W. J. (1987). Co-integration and error correction:
  representation, estimation, and testing. Econometrica 55(2).
- Bailey, D. H. and Lopez de Prado, M. (2014). The deflated Sharpe ratio. Journal
  of Portfolio Management 40(5).
- Johansen, S. (1991). Estimation and hypothesis testing of cointegration vectors
  in Gaussian vector autoregressive models. Econometrica 59(6).
- Avellaneda, M. and Lee, J.-H. (2010). Statistical arbitrage in the US equities
  market. Quantitative Finance 10(7).

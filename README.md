# statarb-agent

An open research project on one question: do cointegration-based pairs among US
large caps still mean-revert after realistic costs, and can a Claude agent that
reads only point-in-time news filter out structural breaks?

Rigour and honesty matter more than returns here. This is paper research only:
no live money, no live trading endpoints, and nothing in this repository is
investment advice.

## Status

Phase 2 of 6 (real pairs). The statistics, the data layer and the command line
are built and tested. The backtester, the dashboard and the agent are not built
yet. `docs/STATUS.md` has the current state; `docs/PROJECT_BRIEF.md` is the plan.

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

## Data sources and limitations

- Prices: Yahoo Finance through the `yfinance` library (no key). It is an
  unofficial interface intended for personal research use; check Yahoo's terms
  before any other use. Downloaded data is never committed to this repository.
- Survivorship bias: free data covers only tickers that still trade. Companies
  that were delisted or acquired are missing, so any universe built from it
  looks better than the real past did. Every real-data result carries this flag.
- Snapshots: each download is stored as an immutable snapshot under `data/raw/`
  with a file hash and a content hash, both checked on every read.
  `data/manifest.json` (committed) lists every snapshot with its source, request,
  retrieval time and hashes.
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
  stats/          ADF, Engle-Granger, hedge ratio, AR(1) half-life, pair statistics
  sources/        price source, snapshot store, manifest, ticker validation
  data/           synthetic pair simulator, calendar alignment, data checks
  study.py        study periods and the test-period lock
  screen.py       the pair screen
  trials.py       the append-only trial log
  analysis.py     one pair end to end
  cli.py          the statarb command
scripts/          measurements cited by the configs
tests/            fixed-seed tests; slow Monte Carlo tests are marked slow
trials/           trials.jsonl, every analysis ever run
docs/             brief, status, sprint plan, handoff notes
```

## References

- Engle, R. F. and Granger, C. W. J. (1987). Co-integration and error correction:
  representation, estimation, and testing. Econometrica 55(2).
- Bailey, D. H. and Lopez de Prado, M. (2014). The deflated Sharpe ratio. Journal
  of Portfolio Management 40(5).
- Avellaneda, M. and Lee, J.-H. (2010). Statistical arbitrage in the US equities
  market. Quantitative Finance 10(7).

# Sprint plan (one week, started 2026-11-10)

This file is the working plan for the accelerated sprint. It is updated at every
commit so the plan survives context compaction and a change of model. Read it
after CLAUDE.md, docs/PROJECT_BRIEF.md, docs/STATUS.md and docs/HANDOFF.md.

The brief is the source of truth. This file does not change phases, gates, rules
or scope. Ideas that would change the plan go under "Proposed changes" below.

## Rules that apply to every milestone

- Deterministic, tested Python computes every number. The LLM computes nothing.
- No look-ahead: every estimator, signal and backtest step uses only rows strictly
  before its as-of date; trades execute at the next bar. Every new estimating or
  signal function has a test that perturbs rows at or after asof.
- The test period (2022-01-01 onward) stays locked. Never unlock it, never write
  PREREGISTRATION.md, never compute on it.
- No parameter, threshold or screen value is chosen by looking at real-pair
  results. Each is derived from theory, synthetic data or random-walk and placebo
  measurements; the derivation is written into the config file and STATUS.md and
  committed before real pairs are run. Every real-data evaluation is appended to
  the trial log.
- Library calls are verified against the installed version, never written from
  memory. No invented numbers, citations or results.
- Fixed seeds; tolerances derived from measurement and written in docstrings.
  Never loosen a tolerance or swap a seed to make a test pass.
- Commits: small, one concern, explicit paths with `git commit --only` (new files
  added by path first). No em dashes or emojis anywhere. Never push. Never rewrite
  history.
- Data and services: only those the brief's data and service policy allows.
- Dependencies: free and permissively licensed only (MIT, BSD, Apache 2.0); each
  new one is recorded with its reason in STATUS.md.
- Quality gate per milestone: `uv run pytest -q`, `uv run pytest -q -m slow`,
  `uv run ruff check`, frontend type check, lint and tests when relevant, the dash
  and emoji scan, and the milestone's acceptance criteria.
- Independent review: the backtester accounting, the walk-forward split logic and
  anything touching the test-period lock are reviewed by a separate reviewer
  subagent that sees only the spec and the code. Reviews are recorded below.
- Before every stop: clean working tree, all tests passing, everything committed
  locally, and docs/HANDOFF.md rewritten from scratch.

## Pre-approved network use (nothing else)

- One fetch each, 2010-01-01 to the lock date, through the price source with its
  pause: SPY, V, MA, KO, PEP, KDP, XOM, CVX, HD, LOW, EWA, EWC (milestone A).
- For milestone D, one fetch each of XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY,
  XLRE, XLC.
- Tickers the user types at run time in the CLI or dashboard.
- The single KO network rerun allowance is spent: the rerun passed on 2026-11-08.
- Anything else, including a re-fetch, needs approval.

## Hard gates (stop, report, wait)

- Network use outside the list above.
- Missing system software, or a dependency that is not free and permissively
  licensed.
- Any choice that would use real results to set a parameter.
- Anything touching the test period or PREREGISTRATION.md.
- Any paid service, API key or cost, including the first real agent run.
- A failing test whose cause cannot be found, or a reviewer finding in dispute.
- After milestone A, after milestone B, and at the end of milestone C.

## Milestone A. Finish Phase 2 (real pairs)

Status: in progress.

Work:
- A1. Record the formation-length measurement; `configs/screen.yaml` with values
  derived from it; `pair_stats` and `apply_screen` with look-ahead tests.
- A2. Append-only JSONL trial log (`trials/trials.jsonl`): schema with label,
  survivorship flag, snapshot ids, config hashes, code version, flags, and unlock
  evidence when the test period is unlocked.
- A3. `configs/data.yaml` for the anomaly thresholds; `configs/pairs.yaml`; CLI
  commands `statarb analyse`, `fetch`, `demo`.
- A4. Fetch the twelve approved tickers once each; run the demo on the formation
  period; report results as they are.
- A5. README: quickstart, data sources, limitations (survivorship bias, yfinance
  personal use only, snapshots and how a fresh clone differs).

Acceptance:
- The brief's Phase 2 gate: all estimates use only data before their as-of date.
- An end-to-end test: perturbing cached rows at or after asof leaves the output
  of `analyse` unchanged.
- Screen values and their derivation are committed before any real pair is run.
- Every demo result is in the trial log with its snapshot ids.

## Milestone B. Backtester (Phase 3, with Kalman and Johansen)

Status: not started.

Work:
- B1. Hedge ratio variants: static OLS, rolling OLS, hand-written numpy Kalman
  filter with a test that recovers a known time-varying beta.
- B2. Signal: the z-score rule from the brief (entry 2, exit 0.5, stop 4), a fixed
  time stop in days from config; half-life is a diagnostic only.
- B3. Walk-forward engine: 252-day formation, 63-day trading, roll; parameters
  frozen within each trading window; next-bar execution.
- B4. Accounting: dollar-neutral (beta-neutral optional), daily mark-to-market,
  cash, gross and net exposure. Costs in `configs/backtest.yaml`: bps per leg per
  trade (sensitivity 0, 10, 20), annual borrow fee, dividends owed on the short leg
  and received on the long leg.
- B5. Metrics with hand-computed tests: Sharpe, Sortino, maximum drawdown, Calmar,
  hit rate, turnover, cost drag, average holding period, beta to SPY,
  Probabilistic and Deflated Sharpe using the trial count from the trial log.
- B6. Controls as rates across fixed seed sets: the synthetic pair shows edge;
  random walks, shuffled-date placebos and V vs XOM do not.
- B7. Johansen basket KO, PEP, KDP through the same backtester.
- B8. Run artifacts in `reports/runs/<run_id>/` (JSON plus Parquet) with
  provenance: git commit, dirty flag, config hash, snapshot ids, trial ids.
- B9. Formation and validation periods only; the CLI opens the validation period
  and STATUS records it. Every evaluated configuration is logged as a trial.

Acceptance:
- The brief's Phase 3 gate: placebo controls show no edge, the synthetic pair
  shows one.
- Reviewer subagent sign-off on accounting, walk-forward splits and lock handling.

## Milestone C. Dashboard (Phase 4b), all 14 sections of docs/DASHBOARD_SPEC.md

Status: not started. Node v26.7.0 and npm 12.0.2 are installed (checked
2026-11-10).

Work:
- C1. FastAPI backend in `src/statarb_agent/api/`; pydantic schemas mirrored as
  TypeScript types with a drift test.
- C2. Frontend in `frontend/`: React, TypeScript, Vite, Tailwind, Plotly, Framer
  Motion, lucide-react, fonts bundled locally.
- C3. `uv run statarb dashboard` builds the frontend if needed, starts the server
  on localhost and opens the browser; `--dev` runs the Vite dev server.
- C4. Component gallery first, screenshot with Playwright at 1440x900, compare
  mood with `design/inspiration/`, iterate, then pages.
- C5. Flows: (1) any two tickers, exploratory analysis with download notice,
  exploratory label and trial-log entry; (2) backtest form with defaults, run as a
  background job with progress; (3) browse runs and compare two side by side;
  (4) provenance hover on every number.
- C6. Pages: overview, pair explorer, cointegration, backtest, controls, agent
  (honest empty state until milestone E), methodology and limitations. 3D views
  per section 14, each with a 2D toggle.
- C7. Screenshots of every page in empty, loading, error and populated states in
  `reports/screenshots/`; the best in the README.

Acceptance: the spec's section 11 checklist.

## Milestone D. Universe strategy (Phase 3b), only if A to C passed

Status: not started.

ETF universe, residual s-scores against sector ETFs and PCA factors, cvxpy
portfolio, cost model. A synthetic universe with known factor structure first, per
the brief's 3b gate. A dashboard page for it.

## Milestone E. Agent scaffolding (Phase 4, free parts only)

Status: not started.

FastMCP server with as-of tools (analyse_pair, run_backtest, get_run, list_runs,
rolling_cointegration, propose_order that only writes `orders/pending.json`), each
logging to JSONL. Agent SDK loop with hooks enforcing limits, a memo skill, and an
offline mock mode for tests. No call to the paid Claude API.

## Progress log

- 2026-11-10. Sprint started. Reconciled the previous session: the KO network
  rerun passed and is recorded (4d05384); the lock follow-ups are committed
  (6ece2e9); the formation-length measurement was run and reported but not yet
  written to STATUS or a config. Baseline: 396 tests pass, ruff clean, tree clean.

- 2026-11-10. A1 done: `configs/screen.yaml` with its derivation, `pair_stats`,
  `apply_screen`, the measurement script and tests. The measurement reproduced
  exactly through the library code. Next: A2, the trial log.

- 2026-11-10. A2 done: the append-only trial log with unlock events. Next: A3,
  `configs/data.yaml`, `configs/pairs.yaml` and the CLI.

- 2026-11-10. A3 done: `configs/data.yaml`, `configs/pairs.yaml`, the analysis
  path, the CLI and the end-to-end look-ahead test. Next: A4, the twelve
  pre-approved downloads and the demo run.

## Reviews

None yet.

## Proposed changes

None yet.

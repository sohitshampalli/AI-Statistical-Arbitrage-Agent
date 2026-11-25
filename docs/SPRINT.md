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

Status: done 2026-11-10. Approved by the user on 2026-11-11.

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

Status: done 2026-11-23 (Phase 3 gate passed). Closed out by the user's
decisions of 2026-11-23, listed in the progress log.

Additions from the user on 2026-11-11:
- Before any backtest on real data, commit `configs/backtest.yaml` with every
  parameter (entry, exit and stop z, the time stop in days, cost levels, borrow
  fee, sizing) and its derivation from theory, synthetic data or placebo runs. No
  value may be changed after seeing real backtest results; any later change is a
  new trial, logged as one.
- Backtest all demo pairs as case studies, plus the controls, whatever their
  screen result. Report the screen status next to each result, and report screened
  pairs separately as the strategy's headline result.
- Every backtest run, including parameter sweeps and cost sensitivities, is
  appended to the trial log, so the Deflated Sharpe ratio uses the real trial
  count.
- Do not rerun `analyse` or `demo` just to inspect results (each run adds a
  trial). Read the stored artifacts and the trial log instead.
- Keep auto-fetch with its notice; `data/raw` must be backed up outside git; the
  trial log stays committed.

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

Status: plan approved 2026-11-23 with the user's decisions below; commit 0 done.
Price source decided 2026-11-25 (stay on the snapshots). Commits 1 to 5 done;
stopped at the commit 5 checkpoint (gallery screenshots and design critique)
for the author's review. Not built yet: the POST job endpoints (analyse and
backtest, with the per-session token and one job at a time), planned with the
pair explorer flows in commit 7.

Decisions of 2026-11-23:
- Licences allowed: MIT, BSD, Apache 2.0, ISC, PSF, Zlib, OFL for fonts only, MPL
  2.0 for dependencies used unmodified, at runtime or in development (widened
  2026-11-23; the full rule is in the brief). Inter and JetBrains Mono (OFL) and
  lucide-react (ISC) approved. Every package and data source in
  docs/THIRD_PARTY.md.
- Installs approved: `uv add fastapi`, the planned npm packages, Playwright's
  Chromium and lighthouse, each checked against the licence rule.
- GET for all reading. POST for analyse and backtest jobs, calling the same
  tested Python, with a confirm dialog showing the trial count before and after
  and a notice before downloading an uncached ticker. Local security, each with a
  test: bind 127.0.0.1 only; reject a foreign Origin or Host; a random
  per-session token in a custom header on every POST; one job at a time; no
  endpoint places orders or touches the test period.
- Surfaces: both built on simulated data first. Real-data rolling cointegration
  (kind diagnostic, not counted) and the real-data parameter surface (every cell
  a counted trial, then a recomputed summary) only after asking, with the trial
  count stated. Both labelled "stability view, not used to choose anything".
- Design: exceptional, not a template. One Plotly template from the tokens;
  type scale, 8 px grid, tabular figures, designed states, reduced motion;
  layouts checked at 1280, 1440 and 1920 px; a design critique in this file after
  each screenshot round, at least two rounds before pages.
- Stops: after commit 5 (gallery screenshots and critique), after commit 9, at
  the end with the section 11 checklist, and before any real-data computation. Node v26.7.0 and npm 12.0.2 are installed (checked
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

- 2026-11-10. A4 and A5 done: twelve tickers fetched once each, the demo run on
  the formation period (all five case-study pairs and the control fail the screen,
  the synthetic pair passes), README written, Phase 2 gate evidence in STATUS.
  Quality gate: 476 fast tests and 4 slow tests pass, ruff clean, scan clean.
  Milestone A complete. Next: milestone B, after the user's go-ahead.
- 2026-11-11. Milestone A approved; milestone B started. B1 done: rolling OLS
  (`rolling_ols_hedge`) and the hand-written Kalman filter (`stats/kalman.py`)
  with exact closed-form tests, a time-varying beta recovery test and look-ahead
  tests.
- 2026-11-11. Johansen wrapper (`stats/johansen.py`) done, with `simulate_basket`
  and `simulate_random_walk_pair` in the simulator.
- 2026-11-11. B2 signal rule done: `signals/zscore.py`, a pure state machine with
  hand-worked tests and a prefix (look-ahead) test.
- 2026-11-11. B5 metrics done: `backtest/metrics.py` with hand-computed tests,
  including Probabilistic and Deflated Sharpe.
- 2026-11-11. B4 accounting done: `backtest/accounting.py`, a daily ledger with a
  hand-booked test, the equity identity and a prefix (look-ahead) test.
- 2026-11-11. B3 walk-forward engine done: `backtest/engine.py` (pair with static,
  rolling and Kalman hedge; Johansen basket) and `backtest/config.py`. Prefix
  invariance holds exactly for every variant: a backtest on the first k rows
  equals the first k rows of the full backtest.
- 2026-11-11. Span metrics (`backtest/summary.py`) and controls
  (`backtest/controls.py`: shuffled-date placebo, simulated control pairs, seed
  batches) done.
- 2026-11-11. `configs/backtest.yaml` committed with every value and its
  derivation, before any real-data backtest. B6 gate tests
  (`tests/test_backtest_gate.py`, slow) pass on seeds 21000 to 21199: cointegrated
  pairs mean net Sharpe 0.86, 0.86, 0.85 (static, rolling, kalman) with at least
  99.5 percent of seeds positive; random walks -0.04, -0.05, -0.05 with gross t
  +0.9, +1.0, +0.5; shuffled placebos -0.05 with gross t +0.1; cointegrated
  baskets 0.53; independent baskets -0.09 with gross t +0.4.
- 2026-11-11. B8 and B9 done: run artifacts (`backtest/runs.py`), the runner
  (`backtest/runner.py`) and the CLI commands `backtest`, `backtest-demo`, `runs`,
  `summarise`. The validation period is open in the CLI. No real-data backtest has
  been run yet; the independent review comes first.
- 2026-11-11. Independent review received (see Reviews). First fix: the
  test-period lock now compares the file on disk with the blob in HEAD, so a git
  index flag cannot hide an uncommitted unlock flag or an edited plan, and an
  empty PREREGISTRATION.md does not count.
- 2026-11-11. Review 1 fixes applied (see Reviews): headline restricted to
  pre-registered runs, one per pair, with validation as its out-of-sample span;
  screened-and-dropped candidates count as trials; the demo screens before it
  backtests; config defaults validated; exposure metrics added. 670 fast tests
  pass. Still no real-data backtest.
- 2026-11-12. Review 1, second pass: the reviewer signed off on running the
  real-data demo backtests and reported four remaining items (N1 to N4). N4 fixed:
  the lock now reads the committed bytes from git and compares them with the bytes
  on disk itself, so a clean filter or a redirected git cannot hide an edit.
- 2026-11-12. N1 to N3 fixed: the headline is stated against the pre-registered
  list in `configs/pairs.yaml`, names every candidate that is missing, unscreened
  or refused, and leaves out any run whose screen result changed after it was
  backtested.
- 2026-11-12. Demo backtests run once at 546443e (90 trial lines, 57 counted);
  trial log committed in 2b92293. All six pre-registered candidates failed the
  screen, so the headline is empty.
- 2026-11-23. Handover from Claude Fable 5.2 to Claude Opus 5.5. The user's
  close-out decisions: the Kalman bound change is accepted as an exception; the
  metrics test is replaced by a deterministic comparison with the exact expected
  maximum; `code_version` no longer counts the trial log, the manifest or run
  folders as code (89 affected trial lines documented, not edited); the last-bar
  exit cost and the basket design are documented with measured numbers, no
  rerun; the lock review is owed before any unlock; the validation period is
  spent for choosing designs; README results section added. Milestone B done.
  Next: the milestone C plan, for the user's approval.
- 2026-11-23. Milestone C commit 0: licence rule in the brief, docs/THIRD_PARTY.md
  (181 Python packages from installed metadata; data-source terms read from the
  official pages), README statement on data use. Findings for the user: seven
  packages outside the allowed list (none replaced); Yahoo's Terms of Service
  section 2(d)(9) prohibits automated collection without express prior
  permission; FRED's terms prohibit storing or caching; Alpaca's terms unread.
  Stopped to ask before installing anything.
- 2026-11-23. The author's decisions on commit 0, carried out in three commits:
  new Yahoo downloads disabled in code (3fbdce8); the licence rule widened and
  arch removed (3a945b9); the replacement-source evaluation recorded in
  docs/THIRD_PARTY.md. No source read meets every requirement: Tiingo needs a
  card and forbids persistent storage, Alpaca's free history starts in 2016,
  EODHD's free tier has one year. Stopped for the author's choice of source.
- 2026-11-25. The author's decisions: stay on the 12 Yahoo snapshots with
  downloads off; paid EODHD rejected; CRSP access through WRDS requested from the
  University of Amsterdam library (nothing changes until access is confirmed).
  Three stale doc lines fixed (3bb25d5). Dashboard commit 1 may start, with the
  adjustments: the "any two tickers" flow offers only cached tickers and explains
  why for any other; the download path stays behind the source interface and
  the `YFINANCE_DOWNLOADS_ENABLED` switch; data provenance (source, snapshot
  date, "downloaded before the terms check") in the provenance drawer and on the
  Methodology page.
- 2026-11-25. Commit 1 (7df34b1): fastapi (MIT) added; `api/store.py` reads
  runs, summaries, the trial log, configs, pairs and the manifest without
  writing, and reports each snapshot's source, download time and whether it
  was downloaded before the terms check; `api/series.py` builds equity and
  drawdown per span, tested against the stored metrics of a real engine run.
- 2026-11-25. Commit 2 (7cfc5f8): pydantic schemas with unknown keys
  forbidden (all 88 stored runs validate), GET routes, errors as a plain
  message with endpoint and run id, foreign Host and Origin refused, API docs
  pages off, `docs/gates.yaml` with evidence tests checked by a test.
- 2026-11-25. Commit 3 (ccd6b2d): JSON Schema export to
  `frontend/src/api/schema.json` with a Python drift test.
- 2026-11-25. Commit 4 (266bd41): frontend scaffold (React, TypeScript 6.0,
  Vite, Tailwind 4, tokens, bundled fonts, ESLint, Vitest, typed client,
  formats of spec section 8, generated types with a drift test) and
  `statarb dashboard` (127.0.0.1 only, builds when out of date, `--dev`).
  One first-version test expectation was wrong (0.2455 rounds to 0.245 in
  binary floating point) and was replaced; no tolerance changed.
  TypeScript is 6.0, not 7.0: typescript-eslint supports below 6.1.
- 2026-11-25. Commit 5 (fe9f967, screenshot clip fix 3bfc18a): the component
  gallery at `/#/dev/components`, the app shell, and the Playwright screenshot
  script (Apache 2.0; Chromium in the user's Playwright cache). Everything
  under reports/ is ignored except the committed 1440 px screenshots; layout
  checks at 1280 and 1920 px go to `reports/screenshots/layout-checks/`.
  Three critique rounds below. Stopped for the author's review.

## Design critique (milestone C)

Screenshots by `npm run screenshots` in frontend/ (Playwright, 1440x900
viewport, full page), compared with the four images in design/inspiration/.
Every populated number in the gallery is read from the API at view time.

What matches the inspiration's mood: near-black page with one soft radial glow
at the top, dark glass cards with thin borders and an inner top highlight, a
pill navigation bar, one cool accent, large tabular KPI numbers, and a node
graph with thin connectors and port dots for the agent flow.

What differs on purpose: no warm orange glow or orange accent (three of the
four images use one; the spec makes blue the accent and keeps orange for
breaks, stops and warnings); KPI numbers in JetBrains Mono with tabular
figures (spec section 4) rather than a proportional display face; no avatar,
chat box, icons-only navigation, sparkline decoration or imagery; every chart
title states a finding and every card carries its source.

Round 1 (first screenshots). Problems found:
1. Cards read as flat grey slabs, not glass.
2. The top glow was barely visible.
3. Section notes were right-aligned and wrapped onto two lines.
4. KPI cards had uneven heights (the label wrapped beside a pill).
5. The table's screen column was a wall of filled red pills.
6. The drawdown panel had the same weight as the equity curve.
7. Long rotated axis titles crowded the chart.
8. The node graph was sparse and its nodes said nothing about their job.

Round 2. Changes: a faint navy tint, a top-down sheen and a stronger top
highlight on cards; a larger, softer top glow; notes under section titles;
pills under the KPI label and cards stretched to equal height; a subtle table
pill (icon plus text, no fill); drawdown in neutral grey, 1 px, 14 percent
fill; panel titles as annotations above each panel and a zero line on the
return panel; one line per node on what it does. Problems left: the node
graph's left nodes overlapped, connectors showed through the translucent
cards and started at node centres; the chart title wrapped too early.

Round 3. Changes: the agent flow laid out left to right in four columns, edge
anchors computed in pixels from the measured width so connectors run from a
node's right edge to the next node's left edge, port dots at each end, opaque
node backgrounds; chart titles up to 96 characters wide. Layouts at 1280 and
1920 px checked: the navigation fits and nothing overflows. The hover
screenshot clip was fixed (3bfc18a).

Open design questions for the author are in docs/HANDOFF.md.

## Reviews

### Review 1: backtester, walk-forward logic and the lock (2026-11-11)

Reviewer: a separate subagent given only the brief, the configs and the code
(it was told not to read STATUS, SPRINT or HANDOFF). It was run before any
real-data backtest. It re-booked the ledger independently for all three hedge
variants (largest profit difference 0.0), checked that position[t] equals
decision[t - 1] on every bar, cross-checked the metrics against scipy and
reproduced the published Deflated Sharpe example (expected maximum 0.11317,
Deflated Sharpe 0.90040).

Verdict: sign-off after fixes. Engine, ledger, z-score rule, estimators and
metric formulas were signed off as they stood: no look-ahead, accounting or
formula defect was found. Every defect that could change a reported number was in
the summary and headline layer, plus one hole in the lock's git check.

Findings and what was done:

| # | Finding | Action |
|---|---|---|
| F1 | The headline reported formation and full spans next to validation; those spans overlap the rows the screen used, so they are in sample for a screened pair | Fixed. Runs and summary record `spans_in_sample_for_screen`; the headline names validation as its out-of-sample span; placebo ranks are given per span |
| F2 | A pair backtested twice (or with legs swapped) was held twice in the headline portfolio | Fixed. One run per ticker set, oldest first; ignored duplicates are listed |
| F3 | The headline said "no pair passed the screen" when pairs had not been screened at all; the demo did not screen real pairs | Fixed. The demo screens any pair with no analysis before backtesting it; the statement distinguishes nothing stored, not analysed and failed |
| F4 | User-chosen (exploratory) pairs could enter the headline | Fixed. The headline holds only pre-registered case-study runs; screened exploratory runs are listed separately |
| F5 | The lock trusted `git status`, which a git index flag can blind; an empty PREREGISTRATION.md was accepted | Fixed in commit 03f91a3: the file on disk must hash to the blob in HEAD, and the plan must contain text |
| F6 | The trial count ignored candidates that were screened and dropped; the headline had no Deflated Sharpe or beta | Fixed. A real candidate analysed but never backtested counts as one trial with an unknown Sharpe; the headline has its own Deflated Sharpe and beta to SPY |
| F7 | A position open on the last bar never pays its exit cost and is not in the trade statistics | Kept, and reported: each run stores `open_at_end` with the cost not charged. Force-closing would make the last rows depend on where the data ends |
| F8 | The basket is not dollar-neutral and trades windows where Johansen finds no relation | Kept as designed and stated as a limitation; net exposure is now a reported metric and each run has a beta to SPY |
| F9 | The config loader accepted a default cost or hedge that the demo never runs | Fixed. The loader refuses both |
| F10 | Docstrings said the Kalman sigma on a bar is known the bar before; it uses that bar's log_b | Fixed the docstrings and added a test of which values on a row may use that row. No tradable look-ahead: decisions fill at the next bar |
| F11 | Backtest trials hard-coded "test period not touched" | Fixed. The flag is derived from the as-of date; a test shows the runner refuses an as-of date past the lock |
| F12 | Minor: the windows table showed the formation fit under names that suggested traded values; run.json is not hash-checked; one-bar trades at window ends; data checks cover the whole window | Columns renamed to `formation_*`; the one-bar trade is pinned by a test and documented as a cost of the rule; the other two are noted as limitations |

Tests added for the untested paths it listed: git index flags and an empty plan
on the lock; duplicate and swapped runs in the headline; the three empty-headline
statements; a locked as-of date in the runner; an engine failure logged as an
error; equity at or below zero; config defaults outside their lists; which
values on a row use that row; beta-neutral sizing with a moving hedge ratio; a
constant leg; three assets with two short legs, costs and dividends; the one-bar
window-end trade.

Second pass (2026-11-12), same reviewer, on commits 03f91a3 and 77549b0. It
re-ran its reproductions against the new code and wrote new ones.

Verdict: sign-off for running the real-data demo backtests. No regression: the
engine, ledger and metric files had an empty diff apart from docstrings and
three column names, and its numbers reproduced to the digit (ledger re-booking
difference 0.0; Deflated Sharpe example 0.11317 and 0.90040). F1, F2, F3, F6, F9,
F10, F11 closed; F7 and F8 closed as documented limitations; F4, F5 and F12
partly closed. Fast suite at that point: 670 passed.

New findings in the second pass and what was done, all before the real run:

| # | Finding | Action |
|---|---|---|
| N4 | The lock still opened through a git clean filter kept out of history: `git status` and `git hash-object` both run the filter, so they agreed with HEAD while the file on disk said true. Redirecting git with GIT_DIR also worked | Fixed in commit 659b1c4: the lock reads the committed bytes with `git cat-file` and compares them with the bytes on disk itself; replace references are off and redirecting GIT_ variables are removed; symlinks are refused. A fake `git` on PATH cannot be stopped and is stated as a limit |
| N1 | The headline's candidates were whatever runs were stored, not the list in `configs/pairs.yaml`; a missing or refused candidate went unmentioned | Fixed: every pre-registered candidate has an entry with a state; missing ones are named with the refusal reason |
| N2 | Screening a pair again after its backtest changed who was in the headline | Fixed: a run whose screen result differs from the one stored with it is left out and named |
| N3 | With one candidate held, the statement was silent about unscreened ones | Fixed: the statement always names candidates with no run, no screen result or a changed screen |

These four fixes were made after the reviewer's sign-off and are covered by new
tests (the three lock tests fail on the previous lock code and pass on the new).
They have not had a third independent pass: the third pass was started on
2026-11-12 and stopped at a usage limit without a report. docs/STATUS.md
("Test-period lock: review still owed") lists what must be reviewed before the
test period is ever unlocked.

## Proposed changes

These are proposals only. Nothing here is implemented; the current plan stands
until the user decides.

1. A per-window gate (proposed 2026-11-11). The screen in `configs/screen.yaml`
   is applied once, to the full formation period, and a pair that fails it is
   simply not part of the strategy. A walk-forward strategy could instead decide
   window by window: trade the next 63 bars only if the 252-bar formation window
   passes a cointegration test. That would be a different, more usual form of the
   strategy (selection inside each formation window, as in the classic pairs
   studies), and it would need its own derivation first: at 252 rows the
   Engle-Granger test has far less power than at 2013, and the half-life cannot be
   used at all (STATUS, half-life bias). It would be a new strategy variant, so
   every run of it would be a new trial. Not implemented: it is not in the brief
   or the sprint plan, and adding it after seeing real results would be choosing a
   design with hindsight. If wanted, its thresholds must be fixed from simulation
   before it touches a real pair.
2. A placebo for the basket (proposed 2026-11-11). Placebos are run for pairs
   only. `shuffle_dates` works on one leg, so a three-leg placebo is a small
   addition; it was left out to keep the number of control runs down.

# Handoff

Rewritten from scratch at every stop. Written 2026-11-23 after milestone C
commit 0 (75becba), at an unplanned stop: the data-source terms check found
questions the author must answer before any install.

## Where things stand

- Last commit: 75becba (licence rule, docs/THIRD_PARTY.md, README data
  statement). Working tree clean. Nothing pushed.
- Tests: `uv run pytest -q` 687 passed; `uv run pytest -q -m slow` 15 passed at
  a41d5b9 (no code changed since); ruff clean.
- Trial log: 97 lines. Do not run analyse, demo, backtest or backtest-demo.
- Waiting for the author on: Yahoo's Terms of Service section 2(d)(9) (automated
  collection), FRED's ban on storing data, and seven packages outside the allowed
  licence list. See docs/THIRD_PARTY.md, "Open questions".

## Finished and verified

- Phase 1 (gate 2026-11-06) and Phase 2 (gate 2026-11-10): statistics, data
  layer, screen, trial log, CLI. See docs/STATUS.md.
- Phase 3 (gate 2026-11-23), sprint milestone B:
  - Hedge ratios: static OLS, rolling OLS, hand-written Kalman filter
    (`stats/hedge_ratio.py`, `stats/kalman.py`); Johansen (`stats/johansen.py`).
  - Z-score rule (`signals/zscore.py`), ledger (`backtest/accounting.py`),
    walk-forward engine (`backtest/engine.py`), metrics with Probabilistic and
    Deflated Sharpe (`backtest/metrics.py`), span metrics (`backtest/summary.py`),
    controls and placebos (`backtest/controls.py`), run artifacts
    (`backtest/runs.py`), runner and headline (`backtest/runner.py`).
  - `configs/backtest.yaml`, fixed before any real-data run, with derivations.
  - Two independent review passes signed off the engine, ledger, signal rule and
    metrics (docs/SPRINT.md, Reviews).
  - One demo run on real data (2026-11-12): all six pre-registered candidates
    failed the screen, so the strategy takes no positions. Exploratory results,
    controls and limitations are in docs/STATUS.md and README.md.
  - Close-out (2026-11-23): deterministic expected-maximum test, `code_version`
    no longer counts output files as code, documentation of exceptions,
    limitations, the spent validation period and the owed lock review.

## Not started

- Milestone C commits 1 to 14 (plan approved 2026-11-23, recorded in
  docs/SPRINT.md). Nothing installed yet (fastapi, npm packages, Playwright).
- Milestone D: universe strategy (Phase 3b). Milestone E: agent scaffolding.

## Open decisions waiting for the user

- The three data-source questions and the seven licence findings in
  docs/THIRD_PARTY.md.
- The proposals in docs/SPRINT.md ("Proposed changes"): a per-window gate and a
  basket placebo. Both would need simulation-only derivations, since the
  validation period is spent.
- Phase 3 one-shot final-test command and Phase 6 live path (docs/STATUS.md).

## Known risks and quirks

- The test-period lock needs an independent review before it is ever unlocked
  (docs/STATUS.md, "Test-period lock: review still owed").
- Trial log lines 9 to 97 say `code_dirty: true` although the code was clean.
  Do not edit them; the cause and fix are in docs/STATUS.md.
- Standing rule: no number goes into a docstring or doc until a command printed it.
- yfinance 1.8.0 returns a seconds-unit, timezone-aware index; `fetch` converts
  to microseconds. statsmodels 0.15.0: `adfuller(..., result_object=True)`,
  `coint` returns an object, `coint_johansen` returns complex eigenvalues (the
  wrapper checks and drops the zero imaginary part). pandas 3.1.1: copy before
  writing to `.to_numpy()` output; Parquet does not keep an index `freq`.
- pytest collects imported names starting with "test" or "Test".
- Ruff is strict (ISC004, TRY004); use `--output-format concise`.
- zsh: no word splitting; a bare `====` in echo fails.
- The reviewer subagent can hit the usage limit mid-review. Ask it for short,
  ordered steps and a partial report when budget runs low.
- Back up `data/raw/` outside git. A re-fetch needs approval and creates new
  snapshot ids.
- Run folders in `reports/runs/` are not in git. If they are lost, the trial log
  still has every metric, but the tables are gone.

## Commands

```sh
source .envrc
uv run pytest -q
uv run pytest -q -m slow                     # about 4.5 minutes
uv run ruff check --output-format concise
uv run statarb runs                          # read stored results, adds no trial
```

Dash and emoji scan (prints nothing when clean):

```sh
grep -nP "\x{2014}|\x{2013}|[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}]" -r src tests configs docs scripts trials CLAUDE.md README.md pyproject.toml
```

## Next task (ready-to-paste prompt)

> Read CLAUDE.md, docs/PROJECT_BRIEF.md, docs/STATUS.md, docs/HANDOFF.md,
> docs/SPRINT.md, docs/THIRD_PARTY.md and docs/DASHBOARD_SPEC.md in full, and look
> at design/inspiration/. Run git status, git --no-pager log --oneline -10,
> uv run pytest -q and uv run ruff check. Do not run analyse, demo, backtest or
> backtest-demo. Apply the author's answers on the open questions in
> docs/THIRD_PARTY.md, then continue milestone C with commit 1 as planned in
> docs/SPRINT.md (fastapi, read-only api/store.py and api/series.py with tests).
> Stop after commit 5 with the gallery screenshots and design critique.

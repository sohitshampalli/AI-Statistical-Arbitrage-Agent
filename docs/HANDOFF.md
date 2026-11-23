# Handoff

Rewritten from scratch at every stop. Written 2026-11-23 at the close of sprint
milestone B (Phase 3), by Claude Opus 5.5, which took over from Claude Fable 5.2
during milestone B.

## Where things stand

- Milestone B is committed in the close-out commit on top of `2b92293`. Run
  `git --no-pager log --oneline -5` for the hash.
- Working tree clean after that commit. Nothing pushed by the assistant.
- Tests at the close-out: `uv run pytest -q` 687 passed, 16 deselected;
  `uv run pytest -q -m slow` 15 passed; `uv run ruff check` clean; no em dashes
  or emojis.
- Trial log: 97 lines. Do not run `analyse`, `demo`, `backtest` or
  `backtest-demo` to look at results; each run adds trials. Use `statarb runs`
  or read `reports/runs/` directly.

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

- Milestone C: dashboard (Phase 4b). Plan proposed in chat on 2026-11-23, waiting
  for the user's approval. Node and npm versions are in that plan.
- Milestone D: universe strategy (Phase 3b). Milestone E: agent scaffolding.

## Open decisions waiting for the user

- Approval of the milestone C plan.
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
> docs/SPRINT.md and docs/DASHBOARD_SPEC.md in full, and look at
> design/inspiration/. Run git status, git --no-pager log --oneline -10,
> uv run pytest -q and uv run ruff check. Do not run analyse, demo, backtest or
> backtest-demo. If the user has approved the milestone C plan, implement it
> commit by commit in the approved order, starting with the API over the stored
> run artifacts and the component gallery. The dashboard only reads
> `reports/runs/` and `trials/trials.jsonl`; it computes no statistic. Follow the
> rules at the top of docs/SPRINT.md, update STATUS.md and SPRINT.md at every
> commit, and rewrite this file at every stop.

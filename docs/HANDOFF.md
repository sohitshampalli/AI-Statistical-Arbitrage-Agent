# Handoff

Rewritten from scratch at every stop. Written 2026-11-10 at the hard gate after
sprint milestone A.

## Where things stand

- Last commit before this file: `b74df9c` (Record the demo run, the Phase 2 gate
  evidence and the README). This file is committed on top of it.
- Working tree clean. Nothing pushed by the assistant.
- Tests: `uv run pytest -q` 476 passed; `uv run pytest -q -m slow` 4 passed;
  `uv run ruff check` clean; no em dashes or emojis.

## Finished and verified

- Phase 1 (gate passed 2026-11-06): simulator, ADF, hedge ratio, Engle-Granger
  in both directions, AR(1) half-life, property test.
- Phase 2 (gate passed 2026-11-10), sprint milestone A:
  - Test-period lock (`study.py`), including the committed-config requirement.
  - Snapshot store, manifest, ticker validation, yfinance price source with a
    forward total-return index (`sources/`).
  - Calendar alignment and data checks (`data/`).
  - `pair_stats` and the screen, with values derived from simulation
    (`configs/screen.yaml` holds the derivation).
  - Append-only trial log (`trials.py`, `trials/trials.jsonl`).
  - CLI `statarb fetch | analyse | demo` (`cli.py`, `analysis.py`).
  - Twelve tickers downloaded once each; demo run recorded; README written.
- Demo result (formation 2010 to 2017, in sample): V/MA, KO/PEP, XOM/CVX, HD/LOW,
  EWA/EWC and the control V/XOM all fail the screen; the synthetic pair passes.
  The table is in docs/STATUS.md and README.md.

## Not started

- Milestone B: backtester (Phase 3) with Kalman and Johansen.
- Milestone C: dashboard (Phase 4b). Node v26.7.0 and npm 12.0.2 are installed.
- Milestone D: universe strategy (Phase 3b). Milestone E: agent scaffolding.

## Open decisions waiting for the user

- Go-ahead to start milestone B (this is the hard gate after milestone A).
- From STATUS "Open decisions": the one-shot final-test command (Phase 3) and the
  separate live paper-trading path (Phase 6). The half-life bias at T = 252 is
  settled for the sprint: a fixed time stop in config, half-life as a diagnostic.

## Known risks and quirks

- yfinance 1.8.0 returns a seconds-unit, timezone-aware index; Parquet has no
  seconds unit, so `fetch` converts to microseconds and notes it in the
  manifest. `raise_errors` is deprecated; the downloader toggles
  `yf.config.debug.hide_exceptions`.
- statsmodels 0.15.0: `adfuller(..., result_object=True)`; `coint` returns a
  CointResult object. pytest turns FutureWarning into an error.
- pandas 3.1.1: `bdate_range` gives `datetime64[us]`; copy-on-write makes
  `.to_numpy()` read-only (copy before writing).
- pytest collects imported names starting with "test" or "Test"; keep such
  names out of library code.
- Ruff is strict here (ISC004 on implicit string concatenation inside
  collections, TRY004). Use `uv run ruff check --output-format concise`.
- zsh: no word splitting, and a bare `====` in echo fails.
- Tests cannot reach the network (autouse guard in `tests/conftest.py`).
- Network allowance: the twelve demo tickers and the KO rerun are spent. Still
  pre-approved for milestone D only: one fetch each of XLB, XLE, XLF, XLI, XLK,
  XLP, XLU, XLV, XLY, XLRE, XLC. Anything else needs the user's approval.
- The snapshot files are under `data/raw/` (gitignored). If they are lost, a
  re-fetch needs approval and creates new snapshot ids.
- Slow tests take about 3 minutes.

## Commands

```sh
source .envrc
uv run pytest -q
uv run pytest -q -m slow
uv run ruff check --output-format concise
uv run statarb demo --offline
uv run statarb analyse KO PEP --offline
uv run python scripts/measure_formation_screen.py   # about 5 minutes
```

Dash and emoji scan (prints nothing when clean):

```sh
grep -nP "\x{2014}|\x{2013}|[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}]" -r src tests configs docs scripts trials CLAUDE.md README.md pyproject.toml
```

## Next task (ready-to-paste prompt)

> Read CLAUDE.md, docs/PROJECT_BRIEF.md, docs/STATUS.md, docs/HANDOFF.md and
> docs/SPRINT.md in full. Run git status, git --no-pager log --oneline -15,
> uv run pytest -q and uv run ruff check. Then start sprint milestone B
> (backtester, Phase 3) exactly as written in docs/SPRINT.md, beginning with B1:
> rolling OLS and a hand-written numpy Kalman filter for the hedge ratio in
> src/statarb_agent/stats/, each with an as-of cutoff, a known-answer test on
> synthetic data and a test that perturbs rows at or after asof. Read
> src/statarb_agent/stats/hedge_ratio.py, stats/_asof.py, stats/pair.py,
> analysis.py and trials.py first. Follow the rules at the top of SPRINT.md:
> verify every library call in the installed version, derive every parameter
> from theory or simulation before running real pairs, log every real-data
> evaluation in the trial log, never touch the test period, commit with
> explicit paths using git commit --only, never push. Update STATUS.md and
> SPRINT.md at every commit and rewrite docs/HANDOFF.md at every stop. Stop at
> the hard gate after milestone B.

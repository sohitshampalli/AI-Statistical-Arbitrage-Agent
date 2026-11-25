# Handoff

Rewritten from scratch at every stop. Written 2026-11-25, at the milestone C
commit 5 checkpoint (component gallery screenshots and design critique).

## Where things stand

- Commits this session: 3bb25d5 (three stale doc lines), fe2c02c (price-source
  decision and CRSP request), dashboard commits 1 to 5: 7df34b1, 7cfc5f8,
  ccd6b2d, 266bd41, fe9f967, plus 3bfc18a (screenshot clip fix) and the
  checkpoint commit on top (these docs and the screenshots). The author pushed
  up to 266bd41; the later commits are local only.
- Tests at the checkpoint: `uv run pytest -q` 734 passed, 16 deselected;
  `uv run pytest -q -m slow` 15 passed; ruff clean; schema export up to date;
  frontend type check and lint clean, Vitest 12 passed, Playwright 4 passed;
  no em dashes or emojis.
- Trial log: 97 lines, unchanged. Do not run analyse, demo, backtest or
  backtest-demo.
- Price data: the 12 Yahoo snapshots only, new downloads off
  (`YFINANCE_DOWNLOADS_ENABLED = False`). The author has requested CRSP through
  WRDS from the University of Amsterdam library; nothing changes until access
  is confirmed.

## Finished and verified

- Phases 1 to 3 (gates 2026-11-06, 2026-11-10, 2026-11-23). See docs/STATUS.md.
- Dashboard backend (`src/statarb_agent/api/`): store, series, schemas, GET
  routes, local-only checks, schema export, `statarb dashboard`.
- Dashboard frontend (`frontend/`): scaffold, tokens, typed client, components
  of spec section 6, app shell, gallery at `/#/dev/components`, screenshot
  script.
- Screenshots (1440 px, committed): `reports/screenshots/gallery-1440.png`,
  `gallery-drawer-1440.png`, `gallery-hover-1440.png`. Layout checks at 1280 and
  1920 px are written to `reports/screenshots/layout-checks/` (gitignored).

## Not started

- Milestone C commits 6 to 14 (docs/SPRINT.md): overview, pair explorer with
  the cached-tickers-only flow, cointegration, backtest and run compare,
  controls, agent and methodology pages, 3D views, accessibility pass, README.
- The POST job endpoints (analyse and backtest) with the per-session token and
  one job at a time; planned with the pair explorer in commit 7.
- Milestone D (universe strategy) and milestone E (agent scaffolding).

## Open decisions waiting for the user

1. The commit 5 review: the gallery screenshots and the critique in
   docs/SPRINT.md ("Design critique"). Commit 6 starts after the author's go.
2. Licences: four dev-only npm packages are outside the named list,
   BlueOak-1.0.0 (`minimatch`, `@isaacs/nonrecursive-glob-match`,
   `graceful-fs`) and CC-BY-4.0 (`caniuse-lite`). All come through approved
   tools (eslint, tailwind) and none ships in the bundle. Accept, or replace
   the tools that pull them in.
3. Design questions:
   - A second chart colour (`--series-2`, orchid #B86BC9) for the second leg
     of a pair. It is not in the spec's tokens; it passed the palette validator
     against the accent and the panel surface.
   - Every stored run is marked stale ("code has changed since"), because the
     runs were made at 546443e. That is true, but it will show on every
     result. An option: mark a run stale only if files under
     `src/statarb_agent` other than `api/` changed since its commit.
   - "Failed screen" is shown in the negative red. Nearly every real result
     failed the screen, so the pages would be mostly red. An option: show a
     failed screen as a neutral fact and keep red for errors and losses.
   - The top bar has two rows (navigation, then data range, commit, lock and
     trial count). It is dense, but every item is in the spec.
4. Still open from before: the proposals in docs/SPRINT.md ("Proposed
   changes"), the Phase 3 one-shot final-test command and the Phase 6 live
   path (docs/STATUS.md).

## Known risks and quirks

- The test-period lock needs an independent review before it is ever unlocked
  (docs/STATUS.md, "Test-period lock: review still owed").
- Trial log lines 9 to 97 say `code_dirty: true` although the code was clean.
  Do not edit them; the dashboard explains them in the trial count panel.
- Standing rule: no number goes into a docstring or doc until a command printed it.
- Take screenshots on a clean tree: the top bar shows "uncommitted changes"
  otherwise. Commit the code first, then run `npm run screenshots`.
- The screenshot script starts `uv run statarb dashboard`, which rebuilds the
  frontend when a source file is newer than `frontend/dist`.
- TypeScript stays on 6.0 until typescript-eslint supports 7.
- `npm install` warns that the fsevents install script is blocked; harmless.
- zsh: no word splitting of a variable; use an array for long path lists in
  `git add` and `git commit --only`.
- yfinance 1.8.0, statsmodels 0.15.0 and pandas 3.1.1 quirks are listed in
  docs/STATUS.md (Notes).
- Back up `data/raw/` outside git; snapshots cannot be re-downloaded.
- Run folders in `reports/runs/` are not in git. If they are lost, the trial log
  still has every metric, but the dashboard's tables and charts are gone.

## Commands

```sh
source .envrc
uv run pytest -q
uv run pytest -q -m slow                     # about 4.5 minutes
uv run ruff check --output-format concise
uv run python -m statarb_agent.api.schema_export --check
uv run statarb dashboard                     # http://127.0.0.1:8000
cd frontend && npm run typecheck && npm run lint && npm test && npm run build
cd frontend && npm run gen:types             # after a schema change
cd frontend && npm run licenses              # npm licence table from the lock file
cd frontend && npm run screenshots           # Playwright; clean tree first
```

Dash and emoji scan (prints nothing when clean):

```sh
grep -nP "\x{2014}|\x{2013}|[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}]" -r src tests configs docs scripts trials CLAUDE.md README.md pyproject.toml frontend/src frontend/scripts frontend/e2e
```

## Next task (ready-to-paste prompt)

> Read CLAUDE.md, docs/PROJECT_BRIEF.md, docs/STATUS.md, docs/HANDOFF.md,
> docs/SPRINT.md, docs/THIRD_PARTY.md and docs/DASHBOARD_SPEC.md in full, and look
> at design/inspiration/ and reports/screenshots/. Run git status,
> git --no-pager log --oneline -10, uv run pytest -q and uv run ruff check. Do
> not run analyse, demo, backtest or backtest-demo. Apply my decisions on the
> commit 5 review (open decisions 1 to 3 in HANDOFF.md), then continue milestone
> C with commit 6 (overview page) and stop after commit 9 as planned.

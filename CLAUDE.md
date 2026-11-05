# statarb-agent
- Python 3.12 managed by uv. Run tests with `uv run pytest`; lint with `uv run ruff check`.
- Package lives in src/statarb_agent/. Keep uv caches inside this folder (see .envrc).
- No look-ahead: every estimator takes an `asof` date and reads only rows before it.
- All statistics live in src/statarb_agent/stats. Notebooks import them; never re-implement.
- Every new function gets a test on synthetic data with a known answer.
- Never call live trading endpoints. Paper trading only.
- Never commit .env, API keys, or data/. Do not edit data/ or reports/ by hand.
- Commit in small chunks with clear messages; never push without asking me.

- Read docs/PROJECT_BRIEF.md at the start of every session. It is the source of truth.
- No emojis and no em dashes anywhere in the project (UI, docs, comments, commit messages).

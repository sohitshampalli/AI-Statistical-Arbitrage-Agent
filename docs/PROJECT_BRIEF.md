# Project brief: statarb-agent

## Goal
Open-source research project: do cointegration-based pairs among US large caps still mean-revert after realistic costs, and can a Claude agent reading only point-in-time news filter out structural breaks? Flagship project for master's applications (econometrics / data science programmes). Rigour and honesty matter more than returns. Paper trading only, never live money. Not investment advice.

## Environment (already set up)
- Folder: ~/statarb-agent (also the git repo; remote origin = github.com/sohitshampalli/AI-Statistical-Arbitrage-Agent, currently private). Branch: main.
- Python 3.12 via uv. Package: src/statarb_agent/ with subpackages data, stats, signals, backtest, risk, agent (each has __init__.py).
- uv caches live inside the folder (.uv-cache, .uv-python via .envrc). Run `source .envrc` in new terminals.
- Installed: numpy 2.5.4, pandas 3.1.1, scipy 1.18.1, statsmodels 0.15.0, arch 8.0.0, yfinance 1.8.0, alpaca-py 0.45.0, pyarrow, matplotlib 3.11.2, pydantic 2.14.3, python-dotenv, typer, claude-agent-sdk 0.2.178, fastmcp 4.1.6. Dev: pytest, hypothesis, ruff, jupyter, ipykernel, nbstripout.
- These versions are newer than your training data. Before using any library function, check its real signature in the installed version (e.g. `uv run python -c "import statsmodels.tsa.stattools as s; help(s.coint)"`). Never write an API call from memory.
- .gitignore ignores .venv, .uv-cache, .uv-python, .envrc, .env, /data/ (top-level only), caches.

## Architecture (one rule above all)
Claude decides and explains; deterministic Python computes and enforces. No statistic is ever computed by the LLM. All math lives in src/statarb_agent/stats and is unit-tested. The later agent calls these functions as MCP/SDK tools; hooks enforce risk limits.

## Math specification (implement exactly; log prices of dividend/split-adjusted closes)
1. ADF on each log price (expect fail to reject) and on returns (expect reject); optionally KPSS (null = stationary).
2. Engle-Granger: OLS p_A = alpha + beta * p_B + eps; ADF on residual with MacKinnon cointegration critical values (use statsmodels.tsa.stattools.coint, whose null is NO cointegration). Run both directions (A on B, B on A) and report both.
3. Johansen (baskets of 3+): statsmodels coint_johansen; trace and max-eigenvalue statistics.
4. Hedge ratio: static OLS from formation window; rolling OLS (past data only); later a Kalman filter with state (alpha_t, beta_t) following a random walk, observation p_A = [1, p_B] . theta + v. Write the Kalman filter by hand in numpy.
5. Mean reversion: fit spread AR(1): S_t = a + b*S_{t-1} + e. theta = -ln(b)/dt, mu = a/(1-b), half-life = ln(2)/theta. Require 0 < b < 1, otherwise return "not mean-reverting". 0 < b < 1 is necessary but not sufficient for mean reversion, so the screening decision belongs to the cointegration tests plus a half-life range, to be decided in Phase 2.
6. Signal: z_t = (S_t - mu_hat_{t-1}) / sigma_hat_{t-1}, estimated only from data before t. Entry |z| > 2, exit |z| < 0.5, stop |z| > 4, time stop about 3 half-lives. Execute at the NEXT bar, never the signal bar.
7. Metrics: annualised Sharpe (mean/std * sqrt(252)), max drawdown, Calmar, hit rate, turnover, cost drag, beta to SPY, Deflated Sharpe ratio (Bailey and Lopez de Prado 2014).

## Hard rules
- No look-ahead: every estimator takes an `asof` argument and uses only rows strictly before it. Every module needs a test that perturbs future rows and asserts today's output is unchanged.
- Costs: model spread/slippage 5-10 bps per leg per trade (sensitivity at 0, 10, 20 bps), short-borrow fee, and dividends owed on the short leg. Defaults must be documented and configurable in configs/.
- Splits (do not touch the test period): formation 2010-2017, validation 2018-2021, test 2022 onward (use once, after PREREGISTRATION.md is committed).
- Never select pairs with hindsight; present famous pairs as case studies.
- Log every trial (pairs, parameters, results) so the Deflated Sharpe ratio can use the number of trials.
- Paper trading only (Alpaca paper); never call live endpoints; never place orders without my explicit approval.
- No secrets in code or git. Keys only in .env (gitignored).
- Parameters live in configs/ YAML, never hard-coded in notebooks.

## Demo universe
V/MA, KO/PEP, XOM/CVX, HD/LOW, EWA/EWC (country ETFs), plus a negative control (V vs XOM, no economic link) and a synthetic pair with known beta and half-life. Expect some famous pairs to fail; a published 2026 case study (Graziano, arXiv 2609.35359) found KO/PEP cointegrated in 2013-2018 but broken out of sample after 2023. Failures are a valid result.

## Phases and gates (do not skip a gate)
1. Foundations: synthetic cointegrated pair simulator + tests. Gate: code recovers true beta and half-life on synthetic data.
2. Real pairs: loader with Parquet cache in data/, stats on each pair. Gate: all estimates use only data before their as-of date.
3. Backtester: walk-forward (252-day formation, 63-day trading, roll), costs, metrics, controls. Gate: placebo controls show no edge, synthetic pair shows one.
4. Agent: MCP tool server + Agent SDK loop + hooks + JSONL log of every tool call. Gate: every number in a memo traces to a logged tool output.
5. Experiment: Kalman, Johansen baskets, LLM break filter evaluated only on data after the model's knowledge cutoff (forward paper trading). Gate: results frozen before paper trades.
6. Paper trading, README, paper.

## Out of scope for now
SEC EDGAR graph / 8-K / Form 4 veto, any live trading, any paid data. Do not add them unless I ask.

## Data notes
yfinance is unofficial and personal-use only; cache to data/ and record source, date and file hash in data/manifest.json. Use adjusted closes for signals. Alpaca free plan: US history from 2016, IEX feed only. Free data has survivorship bias: say so in docs.

## Working style
Small commits with clear messages. Never push without asking. After each change run `uv run pytest -q` and `uv run ruff check` and show the output. If unsure, say so and ask. Never invent results, references or numbers; report only what a command actually printed.

## Dashboard (Phase 4b, after the backtester)
- Local web app, run with one command (`uv run statarb dashboard`), opening on localhost in the browser.
- It only displays results produced by tested code in src/statarb_agent. It never computes statistics itself.
- Pages: pair explorer, cointegration, backtest results, controls, agent memos, methodology and limitations.
- Style: professional and minimal. One neutral palette plus one accent. Chart titles state the finding. Units and data sources are labelled.
- Start with Streamlit or Dash. Reconsider FastAPI plus React only if the core is finished early.
- Add a screenshot of each page to the README.

## Style rules (whole project)
- No emojis and no em dashes anywhere: UI text, README, docs, code comments, commit messages.

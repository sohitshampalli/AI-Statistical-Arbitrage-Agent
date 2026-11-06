# Dashboard specification (Phase 4b)

Read this file only when working on the dashboard. Do not build any dashboard code before the backtester gate (Phase 3) has passed.

## 1. Purpose and audience
- A local web app shown to interviewers and admissions readers. It must make the research legible in a two-minute demo and hold up under a hostile question.
- Premium, calm, professional. Gloss sits on top of rigour and never replaces it.
- Visual references are in design/inspiration/ (local only, not in git). Look at them before designing. Take the mood, not the content: dark glass cards, thin borders, one cool accent, large KPI numbers, a node graph for the agent. Do not copy layouts, assets, icons, copy or branding.

## 2. Non-negotiable principles
1. The UI displays, it never computes. Every number comes from tested code in src/statarb_agent, saved as a result artifact.
2. No invented, placeholder or hard-coded metrics. Empty state beats fake state.
3. Every number carries provenance: run id, git commit, config hash, data manifest hash, period, cost assumption. Shown on hover and in an "About this result" drawer.
4. Honest by default: costs always included, survivorship bias and sample-size warnings always visible where relevant.
5. Synthetic data is always labelled SYNTHETIC in a visible pill.
6. No emojis and no em dashes anywhere (UI copy, code comments, docs, commit messages). Sentence case. Plain words.

## 3. Architecture and stack
- Backend: FastAPI in src/statarb_agent/api/. Read-only JSON endpoints serving result artifacts from reports/ (Parquet or JSON written by the CLI). No endpoint triggers trading. Paper orders are never placed from the UI.
- Frontend: React + TypeScript + Vite in frontend/. Styling with Tailwind CSS and CSS variables for the tokens below. Charts with Plotly or ECharts (pick one, use it everywhere). Animation with Framer Motion, restrained. Icons: one consistent line-icon set (lucide-react).
- Fonts: Inter for text, JetBrains Mono (or Inter with tabular numerals) for numbers. Bundle fonts locally, no CDN, so it runs offline.
- Node.js is required only for the frontend. Commit package-lock.json. Keep node_modules inside frontend/ and gitignored.
- Run: `uv run statarb dashboard` starts FastAPI and serves the built frontend on http://localhost:8000 and opens the browser. A `--dev` flag runs the Vite dev server.
- Contract: one typed JSON schema per endpoint, defined with pydantic in the backend and mirrored as TypeScript types. A test fails if they drift.

## 4. Design tokens (define once as CSS variables, never hard-code colours in components)
Colour (dark theme only for now):
- bg-0: #05070D (page), bg-1: #0A0F1C (panels), bg-2: #101728 (raised)
- surface-glass: rgba(255,255,255,0.04), surface-glass-hover: rgba(255,255,255,0.07)
- border: rgba(255,255,255,0.08), border-strong: rgba(255,255,255,0.16)
- text-primary: #E6EAF2, text-secondary: #8B93A7, text-muted: #5B6377
- accent (cool blue): #4C8DFF, accent-glow: rgba(76,141,255,0.35)
- positive: #34C58E, negative: #E5484D, alert (warm orange, breaks and warnings only): #E8632B
- Colour is never the only carrier of meaning: pair it with an icon, label or sign.
- Minimum contrast 4.5:1 for text.

Type scale (px / weight): display 40/300, h1 28/500, h2 20/500, h3 16/500, body 14/400, label 12/500 uppercase with letter-spacing 0.06em, KPI number 36/400 tabular, table number 13/400 tabular.
Spacing: 4px grid (4, 8, 12, 16, 24, 32, 48, 64). Radii: card 16, control 10, pill 999. Page max width 1440, 12-column grid, 24px gutters.
Glass card: background surface-glass, 1px border, backdrop-filter blur(16px), subtle inner top highlight, soft shadow 0 8px 32px rgba(0,0,0,0.4). Glow only on the single focused or primary element per view.
Page background: bg-0 with one soft radial gradient (accent at 12% opacity) top centre. No busy imagery.
Motion: 150 to 250 ms ease-out for hover and focus, 400 ms for page transitions and chart draw-in. Respect prefers-reduced-motion (disable all non-essential animation). No looping animation except a subtle pulse on a live status dot.

## 5. Layout
- Left icon rail (collapsed, expands on hover) or a top pill navigation, chosen once and used everywhere. Items: Overview, Pair explorer, Cointegration, Backtest, Controls, Agent, Methodology.
- Top bar: project name, current run id and data date range, SYNTHETIC or REAL badge, paper-trading-only badge.
- Content: 12-column grid of glass cards. Desktop first at 1440x900, must work down to 1024 wide. Mobile is out of scope.

## 6. Reusable components (build these first, with a gallery page at /dev/components)
GlassCard, KpiCard (label, value, delta, tooltip with provenance), StatusPill (pass, fail, warn, synthetic, paper), GateBadge (phase gate pass or fail with link to the test), MetricTable (right-aligned tabular numbers, sortable), ChartCard (title states the finding, subtitle gives period and cost assumption, footer gives data source), NodeGraph (agent flow), InlineWarning (survivorship, small sample, regime break), EmptyState (explains which command produces the missing result), Skeleton loader, ProvenanceDrawer.

## 7. Pages and exact content
1. Overview: headline research question; five KPI cards (pairs tested, pairs cointegrated in formation, out-of-sample net Sharpe with Deflated Sharpe beside it, max drawdown, beta to SPY); the phase and gate tracker (which gates passed); a one-paragraph honest summary generated from stored results, not from the LLM at view time.
2. Pair explorer: pair selector (including the control pair and the synthetic pair); log price chart of both legs; spread and z-score chart with entry, exit and stop bands and trade markers; side panel with hedge ratio, half-life, current z.
3. Cointegration: table of Engle-Granger p-values in both directions, Johansen rank, half-life, with a rolling p-value chart per pair that shades regions where cointegration fails (alert colour). Show the formation vs validation vs test period boundaries.
4. Backtest: equity curve with drawdown panel below; cost sensitivity table at 0, 10 and 20 bps; metrics table (Sharpe, Deflated Sharpe, Calmar, hit rate, turnover, cost drag, beta to SPY); trade list with filter; number of trials used for the Deflated Sharpe.
5. Controls: synthetic pair vs independent random walks vs unrelated pair vs shuffled data, side by side, showing edge only where it should exist. This page is the credibility page.
6. Agent: NodeGraph of one agent run (data and stats tool calls flow into the Claude verdict, then the risk limit check, then the proposed paper order). Each node opens the logged tool input and output. Memo viewer where every number links to the tool call that produced it. Clear label that orders require human approval.
7. Methodology and limitations: the maths (rendered with KaTeX), data sources and dates, cost model, look-ahead protections, known limitations (survivorship bias, IEX-only data, small samples, regime change, LLM look-ahead), and the pre-registration file.

## 8. Chart conventions
- Title states the finding (for example "KO and PEP stopped mean-reverting after 2023"), subtitle gives period, sample size and cost assumption, footer gives source.
- Axes labelled with units. ISO dates. Consistent number formats: Sharpe 2 decimals, p-values 3 decimals or scientific below 0.001, returns as percentages with 1 decimal, bps for costs.
- One accent per chart. Alert orange only for breaks and stop-outs. Gridlines at 6% white. Tooltips show exact values and the date.
- Never truncate a bar axis. Annotate regime boundaries and train/validation/test splits.

## 9. States
Loading: skeletons. Empty: explain the CLI command that produces the result. Error: plain message with the failing endpoint and run id. Stale: warn if the result was produced from a different git commit than the current one.

## 10. Accessibility and quality
- Keyboard navigable with visible focus rings. Semantic HTML. Charts have text summaries or data tables.
- Lighthouse accessibility score 90 or higher. No console errors.

## 11. Acceptance checklist (a page is not done until all pass)
1. Screenshots taken at 1440x900 with a headless browser (use Playwright) and compared against design/inspiration/ for mood. List what matches and what deliberately differs.
2. Every number on the page traces to an artifact (show the mapping).
3. No placeholder data, no emojis, no em dashes (run: grep -rn for the em dash character over frontend/src and docs).
4. Frontend type check, lint and unit tests pass. Backend schema tests pass.
5. Page reviewed in empty, loading and error states.
6. Screenshot added to README.

## 12. Two-minute demo script (the dashboard must support this flow)
1. Overview: state the question and the headline honest result.
2. Controls: show the engine finds edge only where it should.
3. Pair explorer and Cointegration: show one pair that works and one famous pair that broke.
4. Backtest: show costs and the Deflated Sharpe.
5. Agent: walk one memo back to its logged tool call.
6. Methodology: show the limitations.

## 13. Out of scope
Live trading, order placement from the UI, user accounts, mobile layout, light theme, real-time streaming.

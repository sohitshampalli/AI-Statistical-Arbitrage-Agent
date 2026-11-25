// /dev/components: every component in each of its states. Populated states
// read live stored results from the API; nothing here is invented.
import type { Data, Layout } from "plotly.js";
import { Bot } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import type { EquitySeries, Gates, RunList, RunManifest, SummaryRow } from "../../api/types";
import { useApi } from "../../api/useApi";
import { ChartCard } from "../../components/ChartCard";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { GateBadge } from "../../components/GateBadge";
import { GlassCard } from "../../components/GlassCard";
import { InlineWarning } from "../../components/InlineWarning";
import { KpiCard } from "../../components/KpiCard";
import { MetricTable, type Column } from "../../components/MetricTable";
import { NodeGraph, type GraphEdge, type GraphNode } from "../../components/NodeGraph";
import { Plot } from "../../components/Plot";
import { SegmentedToggle } from "../../components/SegmentedToggle";
import { Skeleton, SkeletonLines } from "../../components/Skeleton";
import { StatusPill } from "../../components/StatusPill";
import { useProject, type ProvenanceInfo } from "../../context/project";
import { chartColors } from "../../lib/plotTheme";
import { bps, count, fixed, isoDate, percent, sharpe, shortHash } from "../../lib/format";
import { hedgeName, pairName } from "../../lib/runs";
import { useTopBar } from "../../shell/TopBarContext";

const MISSING_RUN = "20991231T000000000000Z-00000000";

function Section({ id, title, note, children }: { id: string; title: string; note?: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="mt-16 first:mt-0">
      <div className="mb-6 border-b border-line pb-3">
        <h2 id={id} className="t-h2 text-ink">{title}</h2>
        {note && <p className="t-body mt-1 max-w-[80ch] text-ink-3">{note}</p>}
      </div>
      {children}
    </section>
  );
}

function StateLabel({ children }: { children: string }) {
  return <p className="t-label mb-2 text-ink-3">{children}</p>;
}

const SWATCHES = [
  ["bg-0", "--bg-0"], ["bg-1", "--bg-1"], ["bg-2", "--bg-2"], ["text-primary", "--text-primary"],
  ["text-secondary", "--text-secondary"], ["text-muted", "--text-muted"], ["accent", "--accent"],
  ["series-2", "--series-2"], ["positive", "--positive"], ["negative", "--negative"], ["alert", "--alert"],
] as const;

const AGENT_NODES: GraphNode[] = [
  { id: "prices", kind: "data", title: "Price data tool", note: "Cached prices before the as-of date", x: 11, y: 17, status: "not_run" },
  { id: "filings", kind: "data", title: "Filings tool", note: "SEC filings accepted before as-of", x: 11, y: 50, status: "not_run" },
  { id: "stats", kind: "stats", title: "Statistics tools", note: "Cointegration, half-life, z-score", x: 11, y: 83, status: "not_run" },
  { id: "verdict", kind: "verdict", title: "Claude verdict", note: "Reads tool outputs; computes nothing", x: 39, y: 50, status: "not_run", primary: true },
  { id: "risk", kind: "risk", title: "Risk limit check", note: "Hooks enforce the limits", x: 65, y: 50, status: "not_run" },
  { id: "order", kind: "order", title: "Proposed paper order", note: "Waits for your approval", x: 89, y: 50, status: "not_run" },
];
const AGENT_EDGES: GraphEdge[] = [
  { from: "prices", to: "verdict" },
  { from: "filings", to: "verdict" },
  { from: "stats", to: "verdict" },
  { from: "verdict", to: "risk" },
  { from: "risk", to: "order" },
];

function provenanceOf(run: RunManifest, label: string, span: string, trialsN?: number | null): ProvenanceInfo {
  return {
    label,
    label2: `${pairName(run.tickers)}, ${hedgeName(run.hedge)}`,
    runId: run.run_id,
    kind: run.kind,
    createdAt: run.created_at_utc,
    provenance: run.provenance,
    period: run.period,
    span,
    costBps: run.cost_bps,
    trialsN: trialsN ?? null,
    trialsNote: trialsN ? "from the latest summary" : null,
    dataSource: run.data_source,
    stale: run.stale,
  };
}

function EquityChart({ series, run, row }: { series: EquitySeries; run: RunManifest; row: SummaryRow | undefined }) {
  const c = chartColors();
  const data = useMemo<Data[]>(
    () => [
      {
        x: series.dates, y: series.equity.map((v) => (v === null ? null : (v - 1) * 100)), type: "scatter", mode: "lines",
        name: "Net of costs", line: { color: c.series1, width: 2 }, hovertemplate: "%{y:.1f}%<extra>net</extra>",
      },
      {
        x: series.dates, y: series.drawdown.map((v) => (v === null ? null : -v * 100)), type: "scatter", mode: "lines",
        name: "Drawdown", yaxis: "y2", line: { color: c.ink2, width: 1 }, fill: "tozeroy", fillcolor: "rgba(139,147,167,0.14)",
        hovertemplate: "%{y:.1f}%<extra>drawdown</extra>", showlegend: false,
      },
    ],
    [series, c.series1, c.ink2],
  );
  const layout = useMemo<Partial<Layout>>(
    () => ({
      showlegend: false,
      margin: { l: 48, r: 16, t: 24, b: 32 },
      yaxis: { domain: [0.36, 1], ticksuffix: "%", zeroline: true, zerolinecolor: c.lineStrong, zerolinewidth: 1 },
      yaxis2: { domain: [0, 0.22], ticksuffix: "%", gridcolor: c.grid, tickfont: { family: "JetBrains Mono", size: 11, color: c.ink2 }, zeroline: false, automargin: true, nticks: 3 },
      xaxis: { anchor: "y2", tickformat: "%Y-%m" },
      annotations: [
        { text: "Cumulative net return, % of capital", xref: "paper", yref: "paper", x: 0, y: 1, yshift: 20, xanchor: "left", showarrow: false, font: { size: 12, color: c.ink2 } },
        { text: "Drawdown from peak, %", xref: "paper", yref: "paper", x: 0, y: 0.22, yshift: 16, xanchor: "left", showarrow: false, font: { size: 12, color: c.ink2 } },
      ],
    }),
    [c.grid, c.ink2, c.lineStrong],
  );
  const m = run.metrics?.validation;
  const dsr = row?.deflated_sharpe?.validation;
  return (
    <ChartCard
      glow
      pills={<><StatusPill kind="exploratory">Exploratory</StatusPill><StatusPill kind="fail">Failed formation screen</StatusPill></>}
      title={`${pairName(run.tickers)}, ${hedgeName(run.hedge)}: ${percent(m?.total_return, true)} on validation, Deflated Sharpe ${fixed(dsr?.dsr, 2)} after ${dsr?.n_trials ?? "n/a"} trials`}
      subtitle={`Validation span ${m?.start} to ${m?.end}, ${count(m?.n_days)} trading days, ${count(m?.n_trades)} closed trades, ${bps(run.cost_bps)} per leg, net of costs and borrow`}
      source={<>Yahoo Finance snapshots downloaded before the terms check; run {run.run_id}, commit {shortHash(run.provenance.code_commit)}</>}
      table={
        <MetricTable
          caption="Validation span metrics"
          rowKey={(r) => r[0]}
          columns={[
            { key: "m", label: "Metric", render: (r: [string, string]) => r[0] },
            { key: "v", label: "Value", align: "right", render: (r: [string, string]) => r[1] },
          ]}
          rows={[
            ["Total return", percent(m?.total_return, true)],
            ["Max drawdown", percent(m?.max_drawdown)],
            ["Net Sharpe", sharpe(m?.sharpe)],
            ["Deflated Sharpe", fixed(dsr?.dsr, 2)],
            ["Trades", count(m?.n_trades)],
          ]}
        />
      }
    >
      <Plot data={data} layout={layout} height={340} summary={`Cumulative net return and drawdown of ${pairName(run.tickers)} on the validation span.`} />
    </ChartCard>
  );
}

export function ComponentGallery() {
  useTopBar({ data: "mixed" });
  const { openProvenance } = useProject();
  const gates = useApi<Gates>("/api/gates");
  const summary = useApi<RunManifest>("/api/summary/latest");
  const runs = useApi<RunList>("/api/runs", { kind: "backtest", label: "case_study", hedge: "static", cost_bps: 10 });
  const firstRun = runs.status === "ready" ? (runs.data.runs[0]?.run_id ?? null) : null;
  const run = useApi<RunManifest>(firstRun ? `/api/runs/${firstRun}` : null);
  const equity = useApi<EquitySeries>(firstRun ? `/api/runs/${firstRun}/series/equity` : null, { span: "validation" });
  const missing = useApi<RunManifest>(`/api/runs/${MISSING_RUN}`);
  const [dim, setDim] = useState<"2d" | "3d">("2d");

  const rows = summary.status === "ready" ? (summary.data.rows ?? []) : [];
  const tableRows = rows.filter((r) => r.data_source !== "synthetic" && r.cost_bps === 10);
  const thisRow = run.status === "ready" ? rows.find((r) => r.run_id === run.data.run_id) : undefined;
  const headline = summary.status === "ready" ? summary.data.headline : null;

  const columns: Column<SummaryRow>[] = [
    { key: "pair", label: "Pair", render: (r) => <span className="font-medium">{pairName(r.tickers)}</span>, sortValue: (r) => pairName(r.tickers) },
    { key: "hedge", label: "Hedge", render: (r) => r.hedge, sortValue: (r) => r.hedge },
    { key: "screen", label: "Screen", render: (r) => <StatusPill subtle kind={r.screen_status === "pass" ? "pass" : "fail"}>{r.screen_status === "pass" ? "Passed" : "Failed"}</StatusPill> },
    { key: "label", label: "Label", render: (r) => r.label.replace("_", " ") },
    { key: "sharpe", label: "Net Sharpe, val.", align: "right", render: (r) => sharpe(r.metrics.validation?.sharpe), sortValue: (r) => r.metrics.validation?.sharpe ?? null },
    { key: "ret", label: "Return, val.", align: "right", render: (r) => percent(r.metrics.validation?.total_return, true), sortValue: (r) => r.metrics.validation?.total_return ?? null },
    { key: "dsr", label: "Deflated Sharpe", align: "right", render: (r) => fixed(r.deflated_sharpe?.validation?.dsr, 2), sortValue: (r) => r.deflated_sharpe?.validation?.dsr ?? null },
  ];

  return (
    <div>
      <header className="max-w-[80ch]">
        <p className="t-label text-accent">Development</p>
        <h1 className="t-display mt-2 text-ink">Component gallery</h1>
        <p className="t-body mt-3 text-ink-2">
          Every component in each of its states. Populated examples read stored results from the API at view time; loading and error states are shown on purpose. Hover a number for its provenance, click it for the full record.
        </p>
      </header>

      <Section id="g-foundations" title="Foundations" note="Tokens from docs/DASHBOARD_SPEC.md, section 4. Inter for text, JetBrains Mono for numbers.">
        <div className="grid grid-cols-12 gap-6">
          <GlassCard className="col-span-7">
            <StateLabel>Type scale</StateLabel>
            <p className="t-display text-ink">Display 40 / 300</p>
            <p className="t-h1 mt-3 text-ink">Heading 1, 28 / 500</p>
            <p className="t-h2 mt-2 text-ink">Heading 2, 20 / 500</p>
            <p className="t-h3 mt-2 text-ink">Heading 3, 16 / 500</p>
            <p className="t-body mt-2 text-ink-2">Body 14 / 400. Sentence case, plain words, no decoration.</p>
            <p className="t-label mt-3 text-ink-2">Label 12 / 500</p>
            <div className="mt-3 flex items-baseline gap-6">
              <span className="t-kpi text-ink">0123456789</span>
              <span className="t-num text-ink-2">0123456789 tabular 13</span>
            </div>
          </GlassCard>
          <GlassCard className="col-span-5">
            <StateLabel>Colour</StateLabel>
            <ul className="grid grid-cols-2 gap-x-4 gap-y-2.5">
              {SWATCHES.map(([name, variable]) => (
                <li key={name} className="flex items-center gap-3">
                  <span className="size-6 shrink-0 rounded-[6px] border border-line-strong" style={{ background: `var(${variable})` }} aria-hidden />
                  <span className="t-num text-ink-2">{name}</span>
                </li>
              ))}
            </ul>
            <p className="t-body mt-4 text-ink-3">Alert orange marks breaks, stops and warnings only. Colour always comes with an icon, a label or a sign.</p>
          </GlassCard>
        </div>
      </Section>

      <Section id="g-status" title="Status pills and gates">
        <div className="flex flex-wrap gap-2.5">
          <StatusPill kind="pass">Passed</StatusPill>
          <StatusPill kind="fail">Failed</StatusPill>
          <StatusPill kind="warn">Before terms check</StatusPill>
          <StatusPill kind="synthetic">Synthetic</StatusPill>
          <StatusPill kind="real">Real data</StatusPill>
          <StatusPill kind="exploratory">Exploratory</StatusPill>
          <StatusPill kind="paper">Paper trading only</StatusPill>
          <StatusPill kind="neutral">Not analysed</StatusPill>
        </div>
        <div className="mt-6 grid grid-cols-4 gap-4">
          {gates.status === "loading" && Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-36" />)}
          {gates.status === "error" && <ErrorState failure={gates.failure} className="col-span-4" />}
          {gates.status === "ready" && gates.data.gates.filter((g) => ["1", "2", "3", "4b"].includes(g.phase)).map((g) => <GateBadge key={g.phase} gate={g} />)}
        </div>
      </Section>

      <Section id="g-kpi" title="KPI cards" note="Populated, empty, loading and error.">
        <div className="grid grid-cols-4 gap-6 [&>div]:flex [&>div]:flex-col [&>div>*:last-child]:flex-1">
          <div>
            <StateLabel>Populated</StateLabel>
            {run.status === "ready" && run.data.metrics?.validation ? (
              <KpiCard
                label="Validation net Sharpe"
                value={sharpe(run.data.metrics.validation.sharpe)}
                pills={<StatusPill kind="exploratory">Exploratory</StatusPill>}
                provenance={provenanceOf(run.data, "Validation net Sharpe", "validation", thisRow?.deflated_sharpe?.validation?.n_trials)}
                footnote={<span>{pairName(run.data.tickers)}, Deflated Sharpe <span className="t-num text-ink">{fixed(thisRow?.deflated_sharpe?.validation?.dsr, 2)}</span></span>}
              />
            ) : (
              <KpiCard label="Validation net Sharpe" value={null} loading />
            )}
          </div>
          <div>
            <StateLabel>Empty, from the stored headline</StateLabel>
            <KpiCard
              label="Out-of-sample net Sharpe"
              value={headline && headline.n_runs > 0 ? "" : null}
              loading={headline === null}
              emptyText={headline ? `No position taken: ${headline.candidate_states.failed ?? 0} of ${headline.n_candidates} pre-registered candidates failed the screen` : undefined}
            />
          </div>
          <div>
            <StateLabel>Loading</StateLabel>
            <KpiCard label="Max drawdown" value={null} loading />
          </div>
          <div>
            <StateLabel>Error, a real failed request</StateLabel>
            {missing.status === "error" ? <ErrorState failure={missing.failure} /> : <Skeleton className="h-[156px]" />}
          </div>
        </div>
      </Section>

      <Section id="g-chart" title="Chart card" note="Title states the finding; subtitle gives span, sample and cost; footer gives the source. Chart or table view.">
        {run.status === "ready" && equity.status === "ready" ? (
          <EquityChart series={equity.data} run={run.data} row={thisRow} />
        ) : run.status === "error" ? (
          <ErrorState failure={run.failure} />
        ) : equity.status === "error" ? (
          <ErrorState failure={equity.failure} />
        ) : (
          <GlassCard>
            <SkeletonLines lines={2} className="max-w-[540px]" />
            <Skeleton className="mt-6 h-[340px]" />
          </GlassCard>
        )}
        <div className="mt-6 flex items-center gap-4">
          <SegmentedToggle label="View" value={dim} onChange={setDim} options={[{ value: "2d", label: "2D" }, { value: "3d", label: "3D" }]} />
          <p className="t-body text-ink-3">Every 3D view has a 2D equivalent and this toggle.</p>
        </div>
      </Section>

      <Section id="g-table" title="Metric table" note="Sortable; numbers right-aligned in tabular figures. Rows from the latest stored summary, 10 bps.">
        <GlassCard padded={false} className="px-3 py-2">
          {summary.status === "loading" && <SkeletonLines lines={6} className="p-4" />}
          {summary.status === "error" && <ErrorState failure={summary.failure} className="m-3" />}
          {summary.status === "ready" && (
            <MetricTable
              caption="Stored backtests at 10 basis points, validation span"
              columns={columns}
              rows={tableRows}
              rowKey={(r) => r.run_id}
              initialSort={{ key: "sharpe", direction: "desc" }}
            />
          )}
        </GlassCard>
      </Section>

      <Section id="g-agent" title="Node graph" note="The agent flow. No agent run exists yet, so every node is not run.">
        <GlassCard>
          <NodeGraph nodes={AGENT_NODES} edges={AGENT_EDGES} height={400} label="Agent flow, not run yet" />
        </GlassCard>
      </Section>

      <Section id="g-states" title="Warnings and empty states">
        <div className="grid grid-cols-2 gap-4">
          <InlineWarning kind="survivorship">Free price data covers only tickers that still trade, so results on real pairs are biased towards survivors.</InlineWarning>
          <InlineWarning kind="small_sample">
            {run.status === "ready" ? `${count(run.data.metrics?.validation?.n_days)} validation days and ${count(run.data.metrics?.validation?.n_trades)} closed trades: one Sharpe estimate on this little data is noisy.` : "Loading the sample size."}
          </InlineWarning>
          <InlineWarning kind="terms">Prices are Yahoo Finance snapshots downloaded before the terms check of 2026-11-23. New downloads are off pending a licensed data source.</InlineWarning>
          <InlineWarning kind="stale">
            {run.status === "ready" ? `Produced at commit ${shortHash(run.data.provenance.code_commit)} on ${isoDate(run.data.created_at_utc)}; ${run.data.stale ? "the code has changed since." : "the code has not changed since."}` : "Loading."}
          </InlineWarning>
        </div>
        <div className="mt-6 grid grid-cols-2 gap-6">
          <EmptyState title="No summary stored yet" command="uv run statarb summarise">
            The overview reads its headline from a stored summary. Writing one reads the run folders and the trial log and adds no trial.
          </EmptyState>
          <EmptyState title="No agent run yet" icon={Bot}>
            The agent arrives in milestone E. Until then this page has nothing to show, and it says so.
          </EmptyState>
        </div>
      </Section>

      <Section id="g-provenance" title="Provenance" note="Every number opens the same record: run, commit, configs, data snapshots, period and cost.">
        <div className="flex items-center gap-4">
          <button
            type="button"
            disabled={run.status !== "ready"}
            onClick={() => run.status === "ready" && openProvenance(provenanceOf(run.data, "Validation net Sharpe", "validation", thisRow?.deflated_sharpe?.validation?.n_trials))}
            className="t-body h-9 rounded-[var(--radius-control)] border border-line-strong bg-glass px-4 text-ink transition-colors duration-150 hover:bg-glass-hover disabled:opacity-50"
          >
            Open the provenance drawer
          </button>
          <p className="t-body text-ink-3">Escape closes it; focus returns here.</p>
        </div>
      </Section>
    </div>
  );
}

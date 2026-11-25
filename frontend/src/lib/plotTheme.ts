// The one Plotly layout and config every chart starts from, built from the
// CSS design tokens so charts and components share one palette.
import type { Config, Layout } from "plotly.js";

function token(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

export function chartColors() {
  return {
    series1: token("--series-1", "#4c8dff"),
    series2: token("--series-2", "#b86bc9"),
    accent: token("--accent", "#4c8dff"),
    alert: token("--alert", "#e8632b"),
    positive: token("--positive", "#34c58e"),
    negative: token("--negative", "#e5484d"),
    ink: token("--text-primary", "#e6eaf2"),
    ink2: token("--text-secondary", "#8b93a7"),
    ink3: token("--text-muted", "#5b6377"),
    grid: token("--gridline", "rgba(255,255,255,0.06)"),
    lineStrong: token("--border-strong", "rgba(255,255,255,0.16)"),
    bg1: token("--bg-1", "#0a0f1c"),
    bg2: token("--bg-2", "#101728"),
  };
}

export function baseLayout(): Partial<Layout> {
  const c = chartColors();
  const axis = {
    gridcolor: c.grid,
    gridwidth: 1,
    zeroline: false,
    linecolor: c.lineStrong,
    linewidth: 1,
    tickcolor: c.lineStrong,
    ticklen: 4,
    tickfont: { family: "JetBrains Mono, ui-monospace, monospace", size: 11, color: c.ink2 },
    title: { font: { family: "Inter, system-ui, sans-serif", size: 12, color: c.ink2 }, standoff: 10 },
    automargin: true,
    showspikes: true,
    spikemode: "across" as const,
    spikethickness: 1,
    spikecolor: c.lineStrong,
    spikedash: "solid",
  };
  return {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "Inter, system-ui, sans-serif", size: 12, color: c.ink2 },
    colorway: [c.series1, c.series2],
    margin: { l: 56, r: 16, t: 8, b: 40 },
    hovermode: "x unified",
    hoverlabel: {
      bgcolor: c.bg2,
      bordercolor: c.lineStrong,
      font: { family: "JetBrains Mono, ui-monospace, monospace", size: 12, color: c.ink },
      align: "left",
    },
    legend: {
      orientation: "h",
      x: 0,
      y: 1.02,
      xanchor: "left",
      yanchor: "bottom",
      font: { size: 12, color: c.ink2 },
      bgcolor: "rgba(0,0,0,0)",
    },
    xaxis: { ...axis, type: "date", hoverformat: "%Y-%m-%d", tickformat: "%Y" },
    yaxis: { ...axis },
    dragmode: "zoom",
  };
}

export const baseConfig: Partial<Config> = {
  displaylogo: false,
  responsive: true,
  modeBarButtonsToRemove: ["select2d", "lasso2d", "autoScale2d", "toggleSpikelines"],
  toImageButtonOptions: { format: "png", scale: 2 },
};

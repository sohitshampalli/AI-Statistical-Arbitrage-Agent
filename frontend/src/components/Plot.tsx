import type { Data, Layout } from "plotly.js";
import { useEffect, useRef, useState } from "react";
import { baseConfig, baseLayout } from "../lib/plotTheme";
import { Skeleton } from "./Skeleton";

type PlotlyModule = typeof import("plotly.js-dist-min").default;
let plotly: Promise<PlotlyModule> | null = null;

/** Plotly is large, so it is loaded once, on the first chart. */
function loadPlotly(): Promise<PlotlyModule> {
  plotly ??= import("plotly.js-dist-min").then((m) => m.default);
  return plotly;
}

function merge(base: Partial<Layout>, extra: Partial<Layout>): Partial<Layout> {
  const out: Record<string, unknown> = { ...base };
  for (const [key, value] of Object.entries(extra)) {
    const current = out[key];
    out[key] =
      value && typeof value === "object" && !Array.isArray(value) && current && typeof current === "object"
        ? { ...(current as object), ...(value as object) }
        : value;
  }
  return out as Partial<Layout>;
}

interface PlotProps {
  data: Data[];
  layout?: Partial<Layout>;
  height?: number;
  /** One sentence describing what the chart shows, for screen readers. */
  summary: string;
}

/** The only chart component: Plotly with the token template. */
export function Plot({ data, layout = {}, height = 320, summary }: PlotProps) {
  const node = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const element = node.current;
    if (!element) return;
    let observer: ResizeObserver | null = null;
    void loadPlotly().then((Plotly) => {
      if (cancelled) return;
      void Plotly.react(element, data, merge(baseLayout(), { ...layout, height }), baseConfig).then(() => {
        if (!cancelled) setReady(true);
      });
      observer = new ResizeObserver(() => {
        void Plotly.Plots.resize(element);
      });
      observer.observe(element);
    });
    return () => {
      cancelled = true;
      observer?.disconnect();
    };
  }, [data, layout, height]);

  useEffect(() => {
    const element = node.current;
    return () => {
      if (element) void loadPlotly().then((Plotly) => Plotly.purge(element));
    };
  }, []);

  return (
    <figure className="relative m-0" style={{ minHeight: height }}>
      <figcaption className="sr-only">{summary}</figcaption>
      {!ready && <Skeleton className="absolute inset-0" label="Loading chart" />}
      <div ref={node} aria-hidden={!ready} />
    </figure>
  );
}

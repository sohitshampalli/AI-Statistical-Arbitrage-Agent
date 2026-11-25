import { Bot, Calculator, Database, FileText, ShieldCheck, type LucideIcon } from "lucide-react";
import { useLayoutEffect, useRef, useState } from "react";
import { cx } from "../lib/cx";

export type NodeKind = "data" | "stats" | "verdict" | "risk" | "order";

export interface GraphNode {
  id: string;
  kind: NodeKind;
  title: string;
  /** Node centre as a percentage of the graph's width (x) and height (y). */
  x: number;
  y: number;
  status: "not_run" | "ok" | "failed" | "blocked";
  /** One line on what the step does. */
  note?: string;
  lines?: Array<{ label: string; value: string }>;
  primary?: boolean;
}

export interface GraphEdge {
  from: string;
  to: string;
}

const ICONS: Record<NodeKind, LucideIcon> = {
  data: Database,
  stats: Calculator,
  verdict: Bot,
  risk: ShieldCheck,
  order: FileText,
};

const STATUS_TEXT = { not_run: "Not run", ok: "Done", failed: "Failed", blocked: "Blocked" } as const;
const WIDTH = 216;
const PRIMARY_WIDTH = 248;

function half(node: GraphNode): number {
  return (node.primary ? PRIMARY_WIDTH : WIDTH) / 2;
}

/**
 * The agent flow, left to right: tool calls feed the verdict, then the risk
 * check, then the proposed paper order. Nodes are buttons, so each can open
 * its logged call. Connectors run from a node's right edge to the next
 * node's left edge, drawn in pixels from the measured width.
 */
export function NodeGraph({ nodes, edges, height = 380, onSelect, label }: { nodes: GraphNode[]; edges: GraphEdge[]; height?: number; onSelect?: (node: GraphNode) => void; label: string }) {
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const element = box.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry?.contentRect.width ?? 0));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const px = (node: GraphNode) => ({ x: (node.x / 100) * width, y: (node.y / 100) * height });

  return (
    <div ref={box} className="relative w-full" style={{ height }} role="group" aria-label={label}>
      {width > 0 && (
        <svg className="absolute inset-0" width={width} height={height} aria-hidden>
          {edges.map((edge) => {
            const a = byId.get(edge.from);
            const b = byId.get(edge.to);
            if (!a || !b) return null;
            const pa = px(a);
            const pb = px(b);
            const x1 = pa.x + half(a);
            const x2 = pb.x - half(b);
            const mid = (x1 + x2) / 2;
            const done = a.status === "ok" && b.status === "ok";
            const stroke = done ? "var(--accent)" : "var(--border-strong)";
            return (
              <g key={`${edge.from}-${edge.to}`}>
                <path d={`M ${x1} ${pa.y} C ${mid} ${pa.y}, ${mid} ${pb.y}, ${x2} ${pb.y}`} fill="none" stroke={stroke} strokeWidth={1.25} strokeDasharray={done ? undefined : "4 4"} />
                <circle cx={x1} cy={pa.y} r={3.5} fill="var(--bg-0)" stroke={stroke} strokeWidth={1.25} />
                <circle cx={x2} cy={pb.y} r={3.5} fill="var(--bg-0)" stroke={stroke} strokeWidth={1.25} />
              </g>
            );
          })}
        </svg>
      )}
      {nodes.map((node) => {
        const Icon = ICONS[node.kind];
        return (
          <button
            key={node.id}
            type="button"
            onClick={onSelect ? () => onSelect(node) : undefined}
            disabled={!onSelect}
            className={cx(
              "absolute -translate-x-1/2 -translate-y-1/2 rounded-[14px] border border-line-strong bg-bg-1 px-4 py-3.5 text-left shadow-[0_8px_24px_rgba(0,0,0,0.35),inset_0_1px_0_rgba(255,255,255,0.06)] transition-colors duration-150",
              node.primary && "glass-glow bg-bg-2 py-5",
              onSelect ? "hover:bg-bg-2" : "cursor-default",
            )}
            style={{ left: `${node.x}%`, top: `${node.y}%`, width: node.primary ? PRIMARY_WIDTH : WIDTH }}
          >
            <span className="flex items-center gap-2">
              <Icon aria-hidden size={15} className={node.primary ? "text-accent" : "text-ink-2"} />
              <span className="t-body font-medium text-ink">{node.title}</span>
            </span>
            {node.note && <span className="t-body mt-1 block text-ink-3">{node.note}</span>}
            <span className="mt-2 flex items-center gap-1.5">
              <span className={cx("size-1.5 rounded-full", node.status === "ok" ? "bg-positive" : node.status === "failed" ? "bg-negative" : node.status === "blocked" ? "bg-alert" : "bg-ink-3")} aria-hidden />
              <span className="t-num text-ink-2">{STATUS_TEXT[node.status]}</span>
            </span>
            {node.lines && node.lines.length > 0 && (
              <span className="t-num mt-2 grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5">
                {node.lines.map((line) => (
                  <span key={line.label} className="contents">
                    <span className="text-ink-3">{line.label}</span>
                    <span className="text-right text-ink">{line.value}</span>
                  </span>
                ))}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

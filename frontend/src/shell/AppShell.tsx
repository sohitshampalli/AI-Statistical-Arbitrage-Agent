import { Lock } from "lucide-react";
import type { ReactNode } from "react";
import { StatusPill } from "../components/StatusPill";
import { Skeleton } from "../components/Skeleton";
import { TrialCountBadge } from "../components/TrialCountBadge";
import { useProject } from "../context/project";
import { cx } from "../lib/cx";
import { isoDate, shortHash } from "../lib/format";
import { GALLERY_PATH, ROUTES, href } from "../router";
import { useTopBarInfo } from "./TopBarContext";

function Brand() {
  return (
    <a href={href("/overview")} className="flex items-center gap-2.5 rounded-[8px]" aria-label="statarb-agent, overview">
      <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden>
        <circle cx="11" cy="11" r="9.25" fill="none" stroke="var(--accent)" strokeWidth="1.5" />
        <path d="M4.5 13.5 C 8 6.5, 14 15.5, 17.5 8.5" fill="none" stroke="var(--text-primary)" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
      <span className="text-[15px] font-medium tracking-[-0.01em] text-ink">statarb-agent</span>
    </a>
  );
}

function Nav({ current }: { current: string }) {
  return (
    <nav aria-label="Pages" className="rounded-full border border-line bg-[rgba(10,15,28,0.6)] p-1 backdrop-blur-[16px]">
      <ul className="flex items-center gap-0.5">
        {ROUTES.map((route) => {
          const active = current === route.path;
          return (
            <li key={route.path}>
              <a
                href={href(route.path)}
                aria-current={active ? "page" : undefined}
                className={cx(
                  "t-body flex h-8 items-center rounded-full px-3.5 whitespace-nowrap transition-colors duration-150",
                  active ? "bg-bg-2 text-ink shadow-[inset_0_0_0_1px_var(--border-strong)]" : "text-ink-2 hover:bg-glass-hover hover:text-ink",
                )}
              >
                {route.label}
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function ContextStrip() {
  const { meta } = useProject();
  const info = useTopBarInfo();
  if (meta.status === "loading") return <Skeleton className="h-4 w-[520px]" />;
  if (meta.status === "error") return <span className="t-num text-negative">Project state unavailable ({meta.failure.endpoint})</span>;
  const m = meta.data;
  return (
    <div className="t-num flex flex-wrap items-center gap-x-5 gap-y-1 text-ink-3">
      <span>
        data <span className="text-ink-2">{isoDate(m.data_first_date)}</span> to <span className="text-ink-2">{isoDate(m.data_last_date)}</span>
      </span>
      <span>
        code <span className="text-ink-2">{shortHash(m.head_commit)}</span>
        {m.head_dirty && <span className="text-alert"> uncommitted changes</span>}
      </span>
      {info.runId && (
        <span>
          run <span className="text-ink-2">{info.runId}</span>
        </span>
      )}
      <span className="inline-flex items-center gap-1.5">
        <Lock aria-hidden size={12} />
        {m.study.test_period_locked ? <>test period locked from <span className="text-ink-2">{m.study.test_start}</span></> : <span className="text-alert">test period unlocked</span>}
      </span>
    </div>
  );
}

export function AppShell({ current, children }: { current: string; children: ReactNode }) {
  const info = useTopBarInfo();
  return (
    <div className="min-h-screen">
      <a href="#main" className="t-body sr-only rounded-[8px] bg-bg-2 px-3 py-2 text-ink focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50">
        Skip to content
      </a>
      <header className="sticky top-0 z-30 border-b border-line bg-[rgba(5,7,13,0.72)] backdrop-blur-[16px]">
        <div className="mx-auto flex max-w-[var(--page-max)] items-center justify-between gap-6 px-8 pt-4 pb-3">
          <Brand />
          <Nav current={current} />
          <div className="flex items-center gap-2">
            {info.data === "synthetic" ? (
              <StatusPill kind="synthetic">Synthetic</StatusPill>
            ) : info.data === "mixed" ? (
              <StatusPill kind="real" title="This page shows real and synthetic results; each is labelled">Real and synthetic</StatusPill>
            ) : (
              <StatusPill kind="real">Real data</StatusPill>
            )}
            <StatusPill kind="paper" title="No order is ever placed from this dashboard">Paper trading only</StatusPill>
          </div>
        </div>
        <div className="mx-auto flex max-w-[var(--page-max)] items-center justify-between gap-6 px-8 pb-3">
          <ContextStrip />
          <TrialCountBadge />
        </div>
      </header>
      <main id="main" className="mx-auto max-w-[var(--page-max)] px-8 pt-10 pb-24">
        {children}
      </main>
      <footer className="mx-auto max-w-[var(--page-max)] px-8 pb-10">
        <p className="t-body text-ink-3">
          Paper research only; not investment advice. Every number on these pages is read from a stored result produced by tested code.{" "}
          <a href={href(GALLERY_PATH)} className="underline decoration-line-strong underline-offset-4 hover:text-ink-2">Component gallery</a>
        </p>
      </footer>
    </div>
  );
}

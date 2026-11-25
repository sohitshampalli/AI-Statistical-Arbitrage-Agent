import { AnimatePresence, motion } from "motion/react";
import { FileWarning, X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";
import type { Snapshot } from "../api/types";
import { useProject } from "../context/project";
import { bps, isoDate, shortHash } from "../lib/format";
import { StatusPill } from "./StatusPill";

function Row({ term, children }: { term: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-ink-3">{term}</dt>
      <dd className="min-w-0 break-all text-ink">{children}</dd>
    </>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-t border-line pt-5">
      <h3 className="t-label text-ink-2">{title}</h3>
      <dl className="t-num mt-3 grid grid-cols-[112px_1fr] gap-x-4 gap-y-2">{children}</dl>
    </section>
  );
}

/** "About this result": every field a number's provenance has (spec section 2). */
export function ProvenanceDrawer() {
  const { drawer: info, closeProvenance, data, meta } = useProject();
  const panel = useRef<HTMLDivElement>(null);
  const opener = useRef<Element | null>(null);

  useEffect(() => {
    if (!info) return;
    opener.current = document.activeElement;
    panel.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeProvenance();
      if (event.key === "Tab" && panel.current) {
        const items = panel.current.querySelectorAll<HTMLElement>("button, a[href], [tabindex='0']");
        const first = items[0];
        const last = items[items.length - 1];
        if (!first || !last) return;
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      if (opener.current instanceof HTMLElement) opener.current.focus();
    };
  }, [info, closeProvenance]);

  const snapshots: Snapshot[] = data.status === "ready" ? data.data.snapshots : [];
  const sources = data.status === "ready" ? data.data.sources : [];
  const head = meta.status === "ready" ? meta.data.head_commit : null;

  return (
    <AnimatePresence>
      {info && (
        <motion.div className="fixed inset-0 z-50" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
          <div className="absolute inset-0 bg-[rgba(2,4,9,0.6)]" onClick={closeProvenance} aria-hidden />
          <motion.div
            ref={panel}
            role="dialog"
            aria-modal="true"
            aria-labelledby="prov-title"
            tabIndex={-1}
            initial={{ x: 32, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 32, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="absolute top-0 right-0 flex h-full w-[440px] max-w-full flex-col gap-5 overflow-y-auto border-l border-line-strong bg-bg-1 px-7 py-6 outline-none"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="t-label text-ink-2">About this result</p>
                <h2 id="prov-title" className="t-h2 mt-1 text-ink">{info.label}</h2>
                {info.label2 && <p className="t-body mt-1 text-ink-2">{info.label2}</p>}
              </div>
              <button type="button" onClick={closeProvenance} aria-label="Close" className="grid size-8 shrink-0 place-items-center rounded-[8px] text-ink-2 hover:bg-glass-hover hover:text-ink">
                <X aria-hidden size={16} />
              </button>
            </div>

            <Section title="Result">
              {info.runId && <Row term="run id">{info.runId}</Row>}
              {info.kind && <Row term="kind">{info.kind}</Row>}
              {info.createdAt && <Row term="created">{isoDate(info.createdAt)}</Row>}
              {info.span && <Row term="span">{info.span}</Row>}
              {info.period && <Row term="period">{`${info.period.name}, ${info.period.start} to before ${info.period.asof}`}</Row>}
              {info.costBps !== undefined && info.costBps !== null && <Row term="cost">{`${bps(info.costBps)} per leg per trade`}</Row>}
              {info.trialsN !== undefined && info.trialsN !== null && <Row term="trials (N)">{`${info.trialsN}${info.trialsNote ? `, ${info.trialsNote}` : ""}`}</Row>}
            </Section>

            <Section title="Code and configs">
              <Row term="commit">
                {shortHash(info.provenance.code_commit)}
                {info.provenance.code_dirty ? " (recorded as dirty)" : ""}
              </Row>
              {head && <Row term="current">{info.provenance.code_commit === head ? "same commit as now" : `code has changed since (now ${shortHash(head)})`}</Row>}
              {Object.entries(info.provenance.config_hashes).map(([name, hash]) => (
                <Row key={name} term={`${name}.yaml`}>{(hash ?? "").slice(0, 12)}</Row>
              ))}
            </Section>

            {info.provenance.snapshot_ids && Object.keys(info.provenance.snapshot_ids).length > 0 && (
              <section className="border-t border-line pt-5">
                <h3 className="t-label text-ink-2">Data</h3>
                <ul className="mt-3 flex flex-col gap-3">
                  {Object.entries(info.provenance.snapshot_ids).map(([ticker, id]) => {
                    const snap = snapshots.find((x) => x.snapshot_id === id);
                    const source = sources.find((x) => x.name === snap?.source);
                    return (
                      <li key={ticker} className="rounded-[8px] border border-line bg-glass px-3 py-2.5">
                        <div className="flex items-center justify-between gap-3">
                          <span className="t-num text-ink">{ticker}</span>
                          {snap?.downloaded_before_terms_check && <StatusPill kind="warn" title={source?.terms_note}>Before terms check</StatusPill>}
                        </div>
                        <p className="t-num mt-1 text-ink-2">
                          {source?.title ?? snap?.source ?? "unknown source"}, downloaded {snap ? isoDate(snap.retrieved_at_utc) : "date unknown"}
                        </p>
                        <p className="t-num mt-0.5 break-all text-ink-3">{id}</p>
                      </li>
                    );
                  })}
                </ul>
                {snapshots.some((x) => x.downloaded_before_terms_check) && (
                  <p className="t-body mt-3 flex gap-2 text-ink-2">
                    <FileWarning aria-hidden size={15} className="mt-0.5 shrink-0 text-alert" />
                    <span>
                      Downloaded before the terms check of {sources[0]?.terms_checked_on ?? "2026-11-23"}. New downloads are off pending a licensed data source; see docs/THIRD_PARTY.md.
                    </span>
                  </p>
                )}
              </section>
            )}
            {info.dataSource === "synthetic" && (
              <section className="border-t border-line pt-5">
                <h3 className="t-label text-ink-2">Data</h3>
                <p className="t-body mt-3 text-ink-2">Simulated with known parameters. Not market data.</p>
              </section>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

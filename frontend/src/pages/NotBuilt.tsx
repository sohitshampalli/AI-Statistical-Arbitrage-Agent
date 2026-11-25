import { Hammer } from "lucide-react";
import { EmptyState } from "../components/EmptyState";

/** A page whose commit has not landed yet. Says so instead of showing anything made up. */
export function NotBuilt({ title }: { title: string }) {
  return (
    <div>
      <h1 className="t-display text-ink">{title}</h1>
      <EmptyState className="mt-8" title="This page is not built yet" icon={Hammer}>
        The dashboard is built in steps (docs/SPRINT.md, milestone C). This page comes in a later commit.
      </EmptyState>
    </div>
  );
}

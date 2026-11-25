import type { ElementType, HTMLAttributes, ReactNode } from "react";
import { cx } from "../lib/cx";

interface GlassCardProps extends HTMLAttributes<HTMLElement> {
  as?: ElementType;
  /** The one focused or primary element of a view; at most one per view. */
  glow?: boolean;
  padded?: boolean;
  children: ReactNode;
}

/** Dark glass panel: the base surface of every card. */
export function GlassCard({ as: Tag = "section", glow = false, padded = true, className, children, ...rest }: GlassCardProps) {
  return (
    <Tag className={cx("glass-card relative", glow && "glass-glow", padded && "p-6", className)} {...rest}>
      {children}
    </Tag>
  );
}

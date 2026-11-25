// Number formats from docs/DASHBOARD_SPEC.md, section 8. These only format
// stored numbers for display; nothing here computes a statistic.

const MINUS = "−";
export const MISSING = "n/a";

function finite(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function signed(text: string, value: number, plus: boolean): string {
  if (value < 0) return MINUS + text.replace(/^-/, "");
  return plus && value > 0 ? `+${text}` : text;
}

/** Fixed decimals with a true minus sign; "n/a" for null, NaN or infinity. */
export function fixed(value: number | null | undefined, decimals: number, plus = false): string {
  if (!finite(value)) return MISSING;
  const text = Math.abs(value) < 0.5 * 10 ** -decimals ? (0).toFixed(decimals) : value.toFixed(decimals);
  return signed(text, Number(text), plus);
}

/** Sharpe ratios: 2 decimals. */
export function sharpe(value: number | null | undefined, plus = false): string {
  return fixed(value, 2, plus);
}

/** p-values: 3 decimals, scientific below 0.001. */
export function pValue(value: number | null | undefined): string {
  if (!finite(value)) return MISSING;
  if (value > 0 && value < 0.001) {
    const [mantissa, exponent] = value.toExponential(2).split("e");
    return `${mantissa}e${(exponent ?? "").replace("-", MINUS)}`;
  }
  return value.toFixed(3);
}

/** Returns and other fractions as percentages with 1 decimal. */
export function percent(fraction: number | null | undefined, plus = false, decimals = 1): string {
  if (!finite(fraction)) return MISSING;
  return `${fixed(fraction * 100, decimals, plus)}%`;
}

/** Costs in basis points. */
export function bps(value: number | null | undefined): string {
  if (!finite(value)) return MISSING;
  return `${Number.isInteger(value) ? value.toFixed(0) : value.toFixed(1)} bps`;
}

/** Whole counts with thin grouping. */
export function count(value: number | null | undefined): string {
  if (!finite(value)) return MISSING;
  return Math.round(value).toLocaleString("en-US");
}

/** ISO date (yyyy-mm-dd) from an ISO date or timestamp string. */
export function isoDate(value: string | null | undefined): string {
  if (!value) return MISSING;
  return value.slice(0, 10);
}

/** First 7 characters of a commit hash. */
export function shortHash(value: string | null | undefined): string {
  if (!value) return MISSING;
  return value === "unknown" ? value : value.slice(0, 7);
}

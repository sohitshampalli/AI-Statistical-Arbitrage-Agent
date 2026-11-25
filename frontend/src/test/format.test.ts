import { describe, expect, it } from "vitest";
import { bps, count, fixed, isoDate, MISSING, percent, pValue, sharpe, shortHash } from "../lib/format";

const M = "−";

describe("number formats (spec section 8)", () => {
  it("formats Sharpe ratios to 2 decimals with a true minus", () => {
    expect(sharpe(0.8404524978819123)).toBe("0.84");
    expect(sharpe(-0.2213)).toBe(`${M}0.22`);
    expect(sharpe(0.55, true)).toBe("+0.55");
    expect(sharpe(-0.004)).toBe("0.00");
    expect(sharpe(null)).toBe(MISSING);
    expect(sharpe(Number.NaN)).toBe(MISSING);
  });

  it("formats p-values to 3 decimals, scientific below 0.001", () => {
    expect(pValue(0.2754)).toBe("0.275");
    expect(pValue(0.001)).toBe("0.001");
    expect(pValue(1.36e-14)).toBe(`1.36e${M}14`);
    expect(pValue(0)).toBe("0.000");
  });

  it("formats returns as percentages with 1 decimal", () => {
    expect(percent(0.17636343012192174)).toBe("17.6%");
    expect(percent(-0.0662751335005691)).toBe(`${M}6.6%`);
    expect(percent(0.041, true)).toBe("+4.1%");
    expect(percent(undefined)).toBe(MISSING);
  });

  it("formats costs, counts, dates and hashes", () => {
    expect(bps(10)).toBe("10 bps");
    expect(bps(7.5)).toBe("7.5 bps");
    expect(count(3021)).toBe("3,021");
    expect(isoDate("2026-11-12T08:15:57.514915+00:00")).toBe("2026-11-12");
    expect(shortHash("546443e31e7b3b6ba3b1493ef43126a2e37bc9c0")).toBe("546443e");
    expect(shortHash("unknown")).toBe("unknown");
    expect(fixed(1.005, 1)).toBe("1.0");
  });
});

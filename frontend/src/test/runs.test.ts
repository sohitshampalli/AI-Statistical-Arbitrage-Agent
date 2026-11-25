import { describe, expect, it } from "vitest";
import { cx } from "../lib/cx";
import { hedgeName, isSynthetic, pairName } from "../lib/runs";

describe("run naming helpers", () => {
  it("names pairs, baskets and summaries", () => {
    expect(pairName(["V", "MA"])).toBe("V / MA");
    expect(pairName(["KO", "PEP", "KDP"])).toBe("KO / PEP / KDP");
    expect(pairName(null)).toBe("summary");
    expect(pairName([])).toBe("summary");
  });
  it("names hedges", () => {
    expect(hedgeName("static")).toBe("static hedge");
    expect(hedgeName("johansen")).toBe("Johansen basket");
    expect(hedgeName(null)).toBe("");
  });
  it("flags synthetic runs by their data source only", () => {
    expect(isSynthetic({ data_source: "synthetic" })).toBe(true);
    expect(isSynthetic({ data_source: "yfinance" })).toBe(false);
    expect(isSynthetic({ data_source: null })).toBe(false);
  });
  it("joins class names and skips falsy ones", () => {
    expect(cx("a", false, null, undefined, "b")).toBe("a b");
  });
});

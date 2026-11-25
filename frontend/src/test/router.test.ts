import { describe, expect, it } from "vitest";
import { href, parseHash } from "../router";

describe("hash router", () => {
  it("defaults to the overview", () => {
    expect(parseHash("").path).toBe("/overview");
    expect(parseHash("#").path).toBe("/overview");
  });
  it("reads a path and its query", () => {
    const route = parseHash("#/backtest?run=abc&span=validation");
    expect(route.path).toBe("/backtest");
    expect(route.params.get("run")).toBe("abc");
    expect(route.params.get("span")).toBe("validation");
  });
  it("builds links", () => {
    expect(href("/pairs")).toBe("#/pairs");
    expect(href("/pairs", { a: "KO", b: "PEP" })).toBe("#/pairs?a=KO&b=PEP");
  });
});

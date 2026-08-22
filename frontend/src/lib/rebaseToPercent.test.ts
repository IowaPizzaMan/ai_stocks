// specs/028-dashboard-tweaks-batch US5 (FR-020, R6) — rebases a price series
// to percentage change from its own first point, so differently-priced ETFs
// share one comparable baseline (clarification Q2).
import { describe, expect, test } from "vitest";
import { rebaseToPercent } from "./rebaseToPercent";

describe("rebaseToPercent", () => {
  test("the first point is always exactly 0", () => {
    const out = rebaseToPercent([
      { date: "2026-01-01", close: 100 },
      { date: "2026-01-02", close: 110 },
    ]);
    expect(out[0]).toEqual({ date: "2026-01-01", pct: 0 });
  });

  test("computes percent change relative to the first close", () => {
    const out = rebaseToPercent([
      { date: "2026-01-01", close: 100 },
      { date: "2026-01-02", close: 110 },
      { date: "2026-01-03", close: 90 },
    ]);
    const pcts = out.map((p) => p.pct);
    expect(pcts[0]).toBeCloseTo(0);
    expect(pcts[1]).toBeCloseTo(10);
    expect(pcts[2]).toBeCloseTo(-10);
  });

  test("empty input returns empty output", () => {
    expect(rebaseToPercent([])).toEqual([]);
  });

  test("a single bar returns one point at 0", () => {
    expect(rebaseToPercent([{ date: "2026-01-01", close: 42 }])).toEqual([
      { date: "2026-01-01", pct: 0 },
    ]);
  });

  test("a first close of 0 returns empty rather than dividing by zero", () => {
    expect(
      rebaseToPercent([
        { date: "2026-01-01", close: 0 },
        { date: "2026-01-02", close: 5 },
      ]),
    ).toEqual([]);
  });

  test("does not mutate the input array", () => {
    const input = [{ date: "2026-01-01", close: 100 }, { date: "2026-01-02", close: 105 }];
    const copy = JSON.parse(JSON.stringify(input));
    rebaseToPercent(input);
    expect(input).toEqual(copy);
  });
});

import { expect, test } from "vitest";
import type { CurvePoint, Spread } from "../api/types";
import { formatBps, formatChange, formatYield, hasOverlay, hasSpreadData } from "./yieldCurve";

function point(overrides: Partial<CurvePoint> = {}): CurvePoint {
  return { maturity: "10Y", months: 120, current: 4.65, month_ago: 4.58, year_ago: null, ...overrides };
}

test("hasOverlay is true when at least one maturity carries a value", () => {
  const curve = [point({ month_ago: 4.58 }), point({ maturity: "30Y", months: 360, month_ago: null })];
  expect(hasOverlay(curve, "month_ago")).toBe(true);
});

test("hasOverlay is false when every maturity is null for that overlay", () => {
  const curve = [point({ year_ago: null }), point({ maturity: "30Y", months: 360, year_ago: null })];
  expect(hasOverlay(curve, "year_ago")).toBe(false);
});

test("hasOverlay is false for an empty curve", () => {
  expect(hasOverlay([], "month_ago")).toBe(false);
});

test("formatBps signs a positive value and formats a negative one", () => {
  expect(formatBps(46)).toBe("+46 bps");
  expect(formatBps(-20)).toBe("-20 bps");
  expect(formatBps(0)).toBe("0 bps");
});

test("formatBps renders an em dash for a missing reading", () => {
  expect(formatBps(null)).toBe("—");
});

test("formatYield renders two decimal places with a percent sign", () => {
  expect(formatYield(4.65)).toBe("4.65%");
  expect(formatYield(4.6)).toBe("4.60%");
});

test("formatYield renders an em dash for a missing reading", () => {
  expect(formatYield(null)).toBe("—");
});

test("formatChange labels a signed change against the prior session", () => {
  expect(formatChange(-4)).toBe("-4 bps vs prior session");
  expect(formatChange(4)).toBe("+4 bps vs prior session");
});

test("formatChange explains a missing prior session rather than showing a dash", () => {
  expect(formatChange(null)).toBe("no prior session");
});

function spread(overrides: Partial<Spread> = {}): Spread {
  return {
    key: "10y-2y", label: "10y – 2y", current_bps: 46, change_bps: -4,
    inverted: false, series: [], ...overrides,
  };
}

test("hasSpreadData is true when current_bps is present", () => {
  expect(hasSpreadData(spread())).toBe(true);
});

test("hasSpreadData is false when current_bps is null (empty collection response)", () => {
  expect(hasSpreadData(spread({ current_bps: null }))).toBe(false);
});

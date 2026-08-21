import { expect, test } from "vitest";
import type { EarningsCalendarEntry } from "../api/types";
import { filterEntries } from "./earningsFilters";

function entry(overrides: Partial<EarningsCalendarEntry> = {}): EarningsCalendarEntry {
  return {
    ticker: "AAA",
    company: "AAA Co",
    sector: "Technology",
    market_cap: 10e9,
    report_date: "2026-08-15",
    eps_estimate: 1.0,
    eps_actual: null,
    revenue_estimate: 1e9,
    revenue_actual: null,
    eps_surprise_pct: null,
    revenue_surprise_pct: null,
    beat: null,
    reporting_state: "upcoming",
    last_updated: "2026-08-17",
    ...overrides,
  };
}

const NO_FILTER = { minRev: 0, minEps: 0, moversOnly: false };

test("min_rev/min_eps at zero keep rows with no figure at all", () => {
  const rows = [entry({ revenue_estimate: null, eps_estimate: null })];
  expect(filterEntries(rows, NO_FILTER)).toHaveLength(1);
});

test("above zero, rows with no revenue figure are excluded", () => {
  const rows = [entry({ revenue_estimate: null, revenue_actual: null })];
  expect(filterEntries(rows, { ...NO_FILTER, minRev: 1 })).toHaveLength(0);
});

test("above zero, rows with no eps figure are excluded", () => {
  const rows = [entry({ eps_estimate: null, eps_actual: null })];
  expect(filterEntries(rows, { ...NO_FILTER, minEps: 0.01 })).toHaveLength(0);
});

test("revenue floor uses actual over estimate when reported", () => {
  const rows = [entry({ revenue_estimate: 1e6, revenue_actual: 50e6 })];
  expect(filterEntries(rows, { ...NO_FILTER, minRev: 10e6 })).toHaveLength(1);
});

test("eps magnitude floor does not filter out a large loss", () => {
  // A company printing -2.50 is material news and must survive a magnitude floor.
  const rows = [entry({ eps_actual: -2.5, eps_estimate: -2.0 })];
  expect(filterEntries(rows, { ...NO_FILTER, minEps: 1.0 })).toHaveLength(1);
});

test("eps magnitude floor excludes a small eps regardless of sign", () => {
  const rows = [entry({ eps_actual: -0.05 })];
  expect(filterEntries(rows, { ...NO_FILTER, minEps: 0.1 })).toHaveLength(0);
});

test("movers toggle excludes upcoming rows with no computable surprise", () => {
  const rows = [entry({ reporting_state: "upcoming", eps_surprise_pct: null, revenue_surprise_pct: null })];
  expect(filterEntries(rows, { ...NO_FILTER, moversOnly: true })).toHaveLength(0);
});

test("movers toggle keeps rows at or above the 10% threshold", () => {
  const rows = [
    entry({ reporting_state: "reported", eps_surprise_pct: 10 }),
    entry({ reporting_state: "reported", eps_surprise_pct: 9.99 }),
  ];
  const out = filterEntries(rows, { ...NO_FILTER, moversOnly: true });
  expect(out).toHaveLength(1);
  expect(out[0].eps_surprise_pct).toBe(10);
});

test("movers toggle uses the max of |eps surprise| and |revenue surprise|", () => {
  const rows = [entry({ reporting_state: "reported", eps_surprise_pct: 1, revenue_surprise_pct: -15 })];
  expect(filterEntries(rows, { ...NO_FILTER, moversOnly: true })).toHaveLength(1);
});

test("filters combine as AND", () => {
  const rows = [
    entry({ revenue_estimate: 5e6, eps_estimate: 0.5 }), // fails revenue floor
    entry({ revenue_estimate: 50e6, eps_estimate: 0.005 }), // fails eps floor
    entry({ revenue_estimate: 50e6, eps_estimate: 0.5 }), // passes both
  ];
  const out = filterEntries(rows, { minRev: 10e6, minEps: 0.01, moversOnly: false });
  expect(out).toHaveLength(1);
});

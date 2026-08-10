import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import type { MarketBreadth } from "../../api/types";
import BreadthDivergenceChart, {
  mergeSeries,
  snapToChartDate,
  zoneBands,
} from "./BreadthDivergenceChart";

afterEach(cleanup);

const osc = (values: number[]) =>
  values.map((value, i) => ({ date: `2026-08-${String(i + 1).padStart(2, "0")}`, value }));

test("zoneBands groups contiguous runs beyond ±60", () => {
  const bands = zoneBands(osc([0, -70, -80, -10, 65, 70, 0]));
  expect(bands).toEqual([
    { start: "2026-08-02", end: "2026-08-03", zone: "oversold" },
    { start: "2026-08-05", end: "2026-08-06", zone: "overbought" },
  ]);
});

test("zoneBands splits when the zone flips without passing through neutral", () => {
  const bands = zoneBands(osc([-70, 70]));
  expect(bands.map((b) => b.zone)).toEqual(["oversold", "overbought"]);
});

test("zoneBands ignores readings inside the bands", () => {
  expect(zoneBands(osc([0, -59, 60, -60]))).toEqual([
    // ±60 itself counts as in-zone; -59 does not
    { start: "2026-08-03", end: "2026-08-03", zone: "overbought" },
    { start: "2026-08-04", end: "2026-08-04", zone: "oversold" },
  ]);
});

test("mergeSeries aligns both panes on one sorted date spine", () => {
  const merged = mergeSeries(
    [
      { date: "2026-08-02", close: 630 },
      { date: "2026-08-01", close: 625 },
    ],
    [
      { date: "2026-08-01", value: -12 },
      { date: "2026-08-03", value: -20 },
    ],
  );
  expect(merged).toEqual([
    { date: "2026-08-01", close: 625, osc: -12 },
    { date: "2026-08-02", close: 630, osc: null },
    { date: "2026-08-03", close: null, osc: -20 },
  ]);
});

test("snapToChartDate moves a marker off a non-trading day to the next session", () => {
  const sessions = ["2026-06-18", "2026-06-22", "2026-06-23"];
  // 2026-06-19 was a market holiday, 06-20/21 a weekend — all snap forward
  expect(snapToChartDate(sessions, "2026-06-19")).toBe("2026-06-22");
  expect(snapToChartDate(sessions, "2026-06-18")).toBe("2026-06-18");
});

test("snapToChartDate falls back to the last session for a date past the window", () => {
  const sessions = ["2026-06-18", "2026-06-22"];
  expect(snapToChartDate(sessions, "2026-06-30")).toBe("2026-06-22");
});

test("snapToChartDate drops resolutions older than the charted window", () => {
  // pinning it to the left edge would read as having resolved there
  expect(snapToChartDate(["2026-06-18", "2026-06-22"], "2026-05-01")).toBeNull();
  expect(snapToChartDate([], "2026-06-18")).toBeNull();
});

const breadth = (overrides: Partial<MarketBreadth> = {}): MarketBreadth => ({
  spy: [
    { date: "2026-08-01", close: 625 },
    { date: "2026-08-02", close: 630 },
  ],
  nymo: [
    { date: "2026-08-01", value: 31.2 },
    { date: "2026-08-02", value: 18.4 },
  ],
  namo: [],
  divergence: {
    type: "bearish",
    description: "SPY made a higher high while NYMO set a lower high",
    price_points: [
      { date: "2026-08-01", value: 625 },
      { date: "2026-08-02", value: 630 },
    ],
    osc_points: [
      { date: "2026-08-01", value: 31.2 },
      { date: "2026-08-02", value: 18.4 },
    ],
  },
  divergence_history: [],
  as_of: "2026-08-02",
  method: "computed_ratio_adjusted",
  ...overrides,
});

test("renders the divergence caption with both anchor values", () => {
  render(<BreadthDivergenceChart breadth={breadth()} />);
  expect(screen.getByText(/bearish divergence/)).toBeDefined();
  expect(screen.getByText(/625 on 2026-08-01/)).toBeDefined();
  expect(screen.getByText(/31.2 → 18.4/)).toBeDefined();
});

test("shows a placeholder instead of empty axes when there is no breadth data", () => {
  render(<BreadthDivergenceChart breadth={breadth({ spy: [], nymo: [] })} />);
  expect(screen.getByText(/no breadth data yet/)).toBeDefined();
});

test("omits the caption when no divergence is in force", () => {
  const none = breadth({
    divergence: { type: "none", description: "none found", price_points: [], osc_points: [] },
  });
  render(<BreadthDivergenceChart breadth={none} />);
  expect(screen.queryByText(/divergence —/)).toBeNull();
});

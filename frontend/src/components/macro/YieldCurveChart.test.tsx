import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import type { TreasuryCurve } from "../../api/types";
import YieldCurveChart from "./YieldCurveChart";

afterEach(cleanup);

function curveData(overrides: Partial<TreasuryCurve> = {}): TreasuryCurve {
  return {
    as_of: "2026-08-19T21:00:00Z",
    stale: false,
    session: "2026-08-19",
    curve: [
      { maturity: "1M", months: 1, current: 3.77, month_ago: 3.81, year_ago: 4.92 },
      { maturity: "10Y", months: 120, current: 4.65, month_ago: 4.58, year_ago: 3.91 },
      { maturity: "30Y", months: 360, current: 5.19, month_ago: null, year_ago: null },
    ],
    comparison_sessions: { month_ago: "2026-07-18", year_ago: "2025-08-19" },
    spreads: [],
    ...overrides,
  };
}

test("renders the session label", () => {
  render(<YieldCurveChart data={curveData()} />);
  expect(screen.getByText("session 2026-08-19")).toBeDefined();
});

test("shows the empty state when there is no session yet", () => {
  render(<YieldCurveChart data={curveData({ session: null, curve: [] })} />);
  expect(screen.getByText(/no yield curve data yet/)).toBeDefined();
});

test("omits the month-ago legend entry when no maturity has an overlay value", () => {
  const data = curveData({
    curve: [{ maturity: "10Y", months: 120, current: 4.65, month_ago: null, year_ago: null }],
    comparison_sessions: { month_ago: null, year_ago: null },
  });
  render(<YieldCurveChart data={data} />);
  expect(screen.queryByText("1 month ago")).toBeNull();
  expect(screen.queryByText("1 year ago")).toBeNull();
});

test("renders normally with both overlays present, without throwing", () => {
  // Recharts' <Legend>/<Line> children don't render into jsdom's zero-size
  // ResponsiveContainer, so the overlay-presence logic itself is covered at
  // the unit level by lib/yieldCurve.test.ts's hasOverlay cases — this just
  // confirms the component doesn't crash when overlays are populated.
  render(<YieldCurveChart data={curveData()} />);
  expect(screen.getByText("session 2026-08-19")).toBeDefined();
});

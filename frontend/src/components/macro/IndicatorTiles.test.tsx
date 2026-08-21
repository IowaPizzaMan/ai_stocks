import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import type { IndicatorTile, RiskPremium } from "../../api/types";
import IndicatorTiles from "./IndicatorTiles";

afterEach(cleanup);

function tile(overrides: Partial<IndicatorTile> = {}): IndicatorTile {
  return {
    key: "inflation", label: "Inflation rate", series: "inflationRate",
    value: 2.27, unit: "%", as_of: "2025-11-19", direction: "down", change: -0.23,
    lagging: true,
    ...overrides,
  };
}

function riskPremium(overrides: Partial<RiskPremium> = {}): RiskPremium {
  return {
    as_of: "2026-08-20T00:00:00Z", stale: false, country: "United States",
    total_equity_risk_premium: 4.46, country_risk_premium: 0.23,
    collected_at: "2026-08-20T00:00:00Z",
    ...overrides,
  };
}

test("renders a tile's value, unit, and as-of date", () => {
  render(<IndicatorTiles indicators={[tile()]} />);
  expect(screen.getByText("Inflation rate")).toBeDefined();
  expect(screen.getByText(/2\.27%/)).toBeDefined();
  expect(screen.getByText("as of 2025-11-19")).toBeDefined();
});

test("omits the direction glyph entirely when direction is null rather than showing flat", () => {
  render(<IndicatorTiles indicators={[tile({ direction: null, change: null })]} />);
  expect(screen.queryByText("▲")).toBeNull();
  expect(screen.queryByText("▼")).toBeNull();
  expect(screen.queryByText("→")).toBeNull();
});

test("shows the lagging marker when the reading is stale, not when it isn't", () => {
  const { rerender } = render(<IndicatorTiles indicators={[tile({ lagging: true })]} />);
  expect(screen.getByText("lagging")).toBeDefined();

  rerender(<IndicatorTiles indicators={[tile({ lagging: false })]} />);
  expect(screen.queryByText("lagging")).toBeNull();
});

test("direction glyphs are not colored good or bad — up and down share styling", () => {
  const { container, rerender } = render(
    <IndicatorTiles indicators={[tile({ direction: "up" })]} />,
  );
  const upClass = container.querySelector("span.ml-2")?.className;

  rerender(<IndicatorTiles indicators={[tile({ direction: "down" })]} />);
  const downClass = container.querySelector("span.ml-2")?.className;

  expect(upClass).toBe(downClass);
});

test("renders the risk premium tile labeled as a valuation input, not a live quote", () => {
  render(<IndicatorTiles indicators={[]} riskPremium={riskPremium()} />);
  expect(screen.getByText("US equity risk premium")).toBeDefined();
  expect(screen.getByText("4.46%")).toBeDefined();
  expect(screen.getByText(/slow-moving valuation input/)).toBeDefined();
});

test("risk premium tile shows unavailable rather than a blank when never fetched", () => {
  render(
    <IndicatorTiles
      indicators={[]}
      riskPremium={riskPremium({ total_equity_risk_premium: null })}
    />,
  );
  expect(screen.getByText("not available yet")).toBeDefined();
});

test("renders no risk premium tile at all when the prop is omitted", () => {
  render(<IndicatorTiles indicators={[]} />);
  expect(screen.queryByText("US equity risk premium")).toBeNull();
});

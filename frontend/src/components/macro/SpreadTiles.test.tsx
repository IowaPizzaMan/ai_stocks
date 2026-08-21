import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import type { Spread } from "../../api/types";
import SpreadTiles from "./SpreadTiles";

afterEach(cleanup);

function spread(overrides: Partial<Spread> = {}): Spread {
  return {
    key: "10y-2y", label: "10y – 2y", current_bps: 46, change_bps: -4,
    inverted: false, series: [
      { date: "2026-08-18", bps: 52 },
      { date: "2026-08-19", bps: 46 },
    ],
    ...overrides,
  };
}

test("renders value and change for each spread", () => {
  render(<SpreadTiles spreads={[spread()]} />);
  expect(screen.getByText("10y – 2y")).toBeDefined();
  expect(screen.getByText("+46 bps")).toBeDefined();
  expect(screen.getByText("-4 bps vs prior session")).toBeDefined();
});

test("shows the inverted badge only when inverted is true", () => {
  const { rerender } = render(<SpreadTiles spreads={[spread({ inverted: false })]} />);
  expect(screen.queryByText("inverted")).toBeNull();

  rerender(<SpreadTiles spreads={[spread({ current_bps: -20, inverted: true })]} />);
  expect(screen.getByText("inverted")).toBeDefined();
});

test("renders an unavailable state when current_bps is null", () => {
  render(<SpreadTiles spreads={[spread({ current_bps: null, change_bps: null, series: [] })]} />);
  expect(screen.getByText("not available yet")).toBeDefined();
  expect(screen.queryByText(/bps vs prior session/)).toBeNull();
});

test("renders one tile per spread, in the order given", () => {
  const spreads = [
    spread({ key: "10y-2y", label: "10y – 2y" }),
    spread({ key: "30y-10y", label: "30y – 10y" }),
    spread({ key: "10y-3m", label: "10y – 3m" }),
  ];
  render(<SpreadTiles spreads={spreads} />);
  expect(screen.getByText("10y – 2y")).toBeDefined();
  expect(screen.getByText("30y – 10y")).toBeDefined();
  expect(screen.getByText("10y – 3m")).toBeDefined();
});

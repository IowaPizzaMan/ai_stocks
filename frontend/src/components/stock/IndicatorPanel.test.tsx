import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import type { OHLCVBar } from "../../api/types";
import type { Timeframe } from "../../lib/strat/displayWindow";
import IndicatorPanel from "./IndicatorPanel";

beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, value: 800 });
  Object.defineProperty(HTMLElement.prototype, "clientHeight", { configurable: true, value: 400 });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
    width: 800, height: 400, top: 0, left: 0, bottom: 400, right: 800, x: 0, y: 0, toJSON: () => {},
  } as DOMRect);
});

afterEach(cleanup);

const bars = (n: number): OHLCVBar[] =>
  Array.from({ length: n }, (_, i) => ({
    date: `2026-01-${String((i % 28) + 1).padStart(2, "0")}`,
    open: 100 + i,
    high: 102 + i,
    low: 98 + i,
    close: 100.5 + i,
    volume: 1000,
  }));

const plenty: Partial<Record<Timeframe, OHLCVBar[]>> = {
  D: bars(120),
  W: bars(120),
  M: bars(120),
  Y: bars(120),
};

test("z-score, stochastic and ATR% each render all four timeframes", () => {
  for (const indicator of ["zscore", "stochastic", "atrPercent"] as const) {
    const { unmount } = render(<IndicatorPanel indicator={indicator} priceData={plenty} />);
    for (const label of ["Daily", "Weekly", "Monthly", "Yearly"]) {
      expect(screen.getByText(label)).toBeTruthy();
    }
    unmount();
  }
});

test("MACD renders only daily, weekly and monthly — never yearly", () => {
  render(<IndicatorPanel indicator="macd" priceData={plenty} />);
  expect(screen.getByText("Daily")).toBeTruthy();
  expect(screen.getByText("Weekly")).toBeTruthy();
  expect(screen.getByText("Monthly")).toBeTruthy();
  expect(screen.queryByText("Yearly")).toBeNull();
});

test("a timeframe without enough history shows the insufficient-history state", () => {
  render(<IndicatorPanel indicator="macd" priceData={{ D: bars(120), W: bars(5), M: bars(3) }} />);
  const notices = screen.getAllByText(/insufficient history/i);
  expect(notices).toHaveLength(2); // weekly and monthly, not daily
});

test("names the bar count a timeframe still needs", () => {
  render(<IndicatorPanel indicator="zscore" priceData={{ D: bars(3) }} />);
  expect(screen.getAllByText(/needs 20 bars/i).length).toBeGreaterThan(0);
});

test("missing price data for a timeframe degrades to the empty state, not a crash", () => {
  expect(() => render(<IndicatorPanel indicator="stochastic" priceData={{}} />)).not.toThrow();
  expect(screen.getAllByText(/insufficient history/i)).toHaveLength(4);
});

test("each indicator row is labeled", () => {
  const titles: Record<string, string> = {
    zscore: "Z-score",
    stochastic: "Stochastic",
    atrPercent: "ATR %",
    macd: "MACD",
  };
  for (const [indicator, title] of Object.entries(titles)) {
    const { unmount } = render(
      <IndicatorPanel indicator={indicator as never} priceData={plenty} />,
    );
    expect(screen.getByText(title)).toBeTruthy();
    unmount();
  }
});

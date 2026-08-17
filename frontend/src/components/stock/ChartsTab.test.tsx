import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import type { OHLCVBar } from "../../api/types";
import type { Timeframe } from "../../lib/strat/displayWindow";
import ChartsTab from "./ChartsTab";

// Recharts' ResponsiveContainer measures its parent, which jsdom reports as 0×0
// and then renders nothing. Give it a real box so the SVG children mount.
beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, value: 800 });
  Object.defineProperty(HTMLElement.prototype, "clientHeight", { configurable: true, value: 400 });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
    width: 800, height: 400, top: 0, left: 0, bottom: 400, right: 800, x: 0, y: 0, toJSON: () => {},
  } as DOMRect);
});

afterEach(cleanup);

function series(count: number, startYear = 2024, step: "day" | "month" | "year" = "day"): OHLCVBar[] {
  return Array.from({ length: count }, (_, i) => {
    let date: string;
    if (step === "year") date = `${startYear + i}-12-31`;
    else if (step === "month") {
      const y = startYear + Math.floor(i / 12);
      date = `${y}-${String((i % 12) + 1).padStart(2, "0")}-28`;
    } else {
      date = new Date(Date.UTC(startYear, 0, 1 + i)).toISOString().slice(0, 10);
    }
    const close = 100 + i;
    return { date, open: close - 1, high: close + 2, low: close - 2, close, volume: 1000 + i };
  });
}

const fullData: Partial<Record<Timeframe, OHLCVBar[]>> = {
  D: series(120),
  W: series(90),
  M: series(40, 2022, "month"),
  Y: series(15, 2010, "year"),
};

test("renders the four timeframe panels in D/W/M/Y order", () => {
  render(<ChartsTab priceData={fullData} />);
  for (const label of ["Daily", "Weekly", "Monthly", "Yearly"]) {
    expect(screen.getAllByText(label).length).toBeGreaterThan(0);
  }
});

test("renders price and volume ROC panels below the charts", () => {
  render(<ChartsTab priceData={fullData} />);
  expect(screen.getByText(/rate of change/i)).toBeTruthy();
  expect(screen.getByText(/price ROC/i)).toBeTruthy();
  expect(screen.getByText(/volume ROC/i)).toBeTruthy();
});

test("renders the indicator rows", () => {
  render(<ChartsTab priceData={fullData} />);
  expect(screen.getByText("Z-score")).toBeTruthy();
  expect(screen.getByText("Stochastic")).toBeTruthy();
  expect(screen.getByText("ATR %")).toBeTruthy();
  expect(screen.getByText("MACD")).toBeTruthy();
});

test("shows the TFC banner only when a status is supplied", () => {
  const { unmount } = render(<ChartsTab priceData={fullData} />);
  expect(screen.queryByText(/Full TFC/)).toBeNull();
  unmount();

  render(<ChartsTab priceData={fullData} tfcStatus="full_bullish" />);
  expect(screen.getByText(/Full TFC — bullish/)).toBeTruthy();
});

test("renders without price data instead of throwing", () => {
  render(<ChartsTab priceData={{}} />);
  expect(screen.getAllByText("no price data").length).toBeGreaterThan(0);
});

// --- US2: monthly/yearly candle counts --------------------------------------

const candleCount = (container: HTMLElement) =>
  container.querySelectorAll("rect.candle-body").length;

test("monthly panel plots ~36 candles — one per month over three years", () => {
  // 60 months supplied; the monthly display window trims to the last 36
  const { container } = render(<ChartsTab priceData={{ M: series(60, 2020, "month") }} />);
  expect(candleCount(container)).toBe(36);
});

test("yearly panel plots at most fifteen candles — one per year", () => {
  const { container } = render(<ChartsTab priceData={{ Y: series(25, 2000, "year") }} />);
  expect(candleCount(container)).toBe(15);
});

test("short history renders every available candle rather than padding", () => {
  const { container } = render(<ChartsTab priceData={{ Y: series(3, 2023, "year") }} />);
  expect(candleCount(container)).toBe(3);
});

test("short history renders every available period without error", () => {
  const shortData: Partial<Record<Timeframe, OHLCVBar[]>> = {
    M: series(8, 2025, "month"),
    Y: series(2, 2024, "year"),
  };
  expect(() => render(<ChartsTab priceData={shortData} />)).not.toThrow();
  expect(screen.getAllByText("Monthly").length).toBeGreaterThan(0);
});

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import type { EarningsCalendarEntry } from "../../api/types";
import EarningsTable, { formatCompact } from "./EarningsTable";

afterEach(cleanup);

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

function renderTable(entries: EarningsCalendarEntry[], onQueueTicker = vi.fn()) {
  render(
    <MemoryRouter>
      <EarningsTable
        entries={entries}
        isLoading={false}
        queuedTickers={new Set()}
        onQueueTicker={onQueueTicker}
      />
    </MemoryRouter>,
  );
}

// --- formatCompact ---------------------------------------------------------------------

test("formatCompact renders null as an em dash, not 0 or blank", () => {
  expect(formatCompact(null)).toBe("—");
});

test("formatCompact abbreviates large values", () => {
  expect(formatCompact(2.8e9)).toBe("$2.8B");
});

// --- reporting_state rendering (US2) ----------------------------------------------------

test("upcoming row shows estimates and placeholders for actual/surprise, never 0 or blank", () => {
  renderTable([
    entry({ ticker: "UPC", reporting_state: "upcoming", eps_estimate: 1.19, eps_actual: null,
            revenue_estimate: 15e9, revenue_actual: null, eps_surprise_pct: null, beat: null }),
  ]);
  const row = screen.getByTestId("earnings-row");
  expect(row.getAttribute("data-reporting-state")).toBe("upcoming");
  expect(row.textContent).toContain("1.19");
  // both the EPS-actual placeholder and the surprise placeholder render "—"
  const placeholders = row.querySelectorAll('[class*="text-zinc-600"]');
  expect(placeholders.length).toBeGreaterThan(0);
  expect(row.textContent).not.toMatch(/\b0(\.00)?\b.*surprise/i);
  expect(screen.queryByTestId("surprise-beat")).toBeNull();
  expect(screen.queryByTestId("surprise-miss")).toBeNull();
});

test("reported beat row shows actuals and a visually distinct beat surprise", () => {
  renderTable([
    entry({
      ticker: "BIG", reporting_state: "reported",
      eps_estimate: 1.0, eps_actual: 1.2, eps_surprise_pct: 20.0, beat: true,
      revenue_estimate: 10e9, revenue_actual: 11e9, revenue_surprise_pct: 10.0,
    }),
  ]);
  const row = screen.getByTestId("earnings-row");
  expect(row.textContent).toContain("1.20");
  const beatEls = screen.getAllByTestId("surprise-beat");
  expect(beatEls.length).toBeGreaterThan(0);
  // color class must differ from the miss/unavailable treatment, not just the text
  expect(beatEls[0].className).toContain("emerald");
  expect(screen.queryByTestId("surprise-miss")).toBeNull();
});

test("reported miss row is styled distinctly from a beat", () => {
  renderTable([
    entry({
      ticker: "MID", reporting_state: "reported",
      eps_estimate: 1.0, eps_actual: 0.8, eps_surprise_pct: -20.0, beat: false,
    }),
  ]);
  const missEls = screen.getAllByTestId("surprise-miss");
  expect(missEls.length).toBeGreaterThan(0);
  expect(missEls[0].className).toContain("red");
  expect(screen.queryByTestId("surprise-beat")).toBeNull();
});

test("a null surprise (missing/zero estimate) renders as unavailable, never a beat", () => {
  renderTable([
    entry({ ticker: "NOCOV", reporting_state: "reported", eps_actual: 0.06, eps_estimate: null,
            eps_surprise_pct: null, beat: null }),
  ]);
  expect(screen.getAllByTestId("surprise-unavailable").length).toBeGreaterThan(0);
  expect(screen.queryByTestId("surprise-beat")).toBeNull();
});

test("awaiting row is visually distinct and never rendered as a miss", () => {
  renderTable([
    entry({ ticker: "WAIT", reporting_state: "awaiting", eps_actual: null, revenue_actual: null }),
  ]);
  const row = screen.getByTestId("earnings-row");
  expect(row.getAttribute("data-reporting-state")).toBe("awaiting");
  expect(screen.getByTestId("awaiting-badge")).toBeTruthy();
  expect(screen.queryByTestId("surprise-miss")).toBeNull();
});

// --- ordering (US3, FR-019) -------------------------------------------------------------

test("renders entries in the given order without re-sorting", () => {
  renderTable([
    entry({ ticker: "ZZZ", market_cap: 1e9 }),
    entry({ ticker: "AAA", market_cap: 100e9 }),
    entry({ ticker: "MMM", market_cap: 50e9 }),
  ]);
  const tickers = screen.getAllByTestId("earnings-row").map((r) => r.querySelector("a")?.textContent);
  expect(tickers).toEqual(["ZZZ", "AAA", "MMM"]);
});

// --- ticker links (US4) ------------------------------------------------------------------

test("ticker renders as a link to the stock detail page", () => {
  renderTable([entry({ ticker: "NVDA" })]);
  const link = screen.getByRole("link", { name: "NVDA" });
  expect(link.getAttribute("href")).toBe("/stock/NVDA");
});

test("clicking the ticker link does not trigger the row's queue action", () => {
  const onQueueTicker = vi.fn();
  renderTable([entry({ ticker: "NVDA" })], onQueueTicker);
  fireEvent.click(screen.getByRole("link", { name: "NVDA" }));
  expect(onQueueTicker).not.toHaveBeenCalled();
});

test("clicking the queue button does not navigate and does not touch the ticker link", () => {
  const onQueueTicker = vi.fn();
  renderTable([entry({ ticker: "NVDA" })], onQueueTicker);
  fireEvent.click(screen.getByRole("button", { name: /queue/i }));
  expect(onQueueTicker).toHaveBeenCalledWith("NVDA");
});

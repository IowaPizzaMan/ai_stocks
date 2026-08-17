import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import type { InsiderQuarterStats, InstitutionalReport } from "../../api/types";
import InsiderFlowCharts from "./InsiderFlowCharts";
import InstitutionalFlowVisuals from "./InstitutionalFlowVisuals";

beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, value: 800 });
  Object.defineProperty(HTMLElement.prototype, "clientHeight", { configurable: true, value: 400 });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
    width: 800, height: 400, top: 0, left: 0, bottom: 400, right: 800, x: 0, y: 0, toJSON: () => {},
  } as DOMRect);
});

afterEach(cleanup);

const quarter = (
  year: number,
  q: number,
  acquired: number,
  disposed: number,
): InsiderQuarterStats => ({
  year,
  quarter: q,
  acquired_transactions: 5,
  disposed_transactions: 5,
  acquired_disposed_ratio: disposed ? acquired / disposed : 0,
  total_acquired: acquired,
  total_disposed: disposed,
  total_purchases: 1,
  total_sales: 1,
});

// --- Insider ----------------------------------------------------------------

test("insider flow reads net disposed when selling dominates recent quarters", () => {
  render(
    <InsiderFlowCharts
      stats={[quarter(2026, 2, 10_000, 900_000), quarter(2026, 1, 5_000, 500_000)]}
    />,
  );
  expect(screen.getByText(/net disposed/i)).toBeTruthy();
});

test("insider flow reads net acquired when buying dominates", () => {
  render(
    <InsiderFlowCharts
      stats={[quarter(2026, 2, 900_000, 10_000), quarter(2026, 1, 500_000, 5_000)]}
    />,
  );
  expect(screen.getByText(/net acquired/i)).toBeTruthy();
});

test("insider flow labels the aggregates as covering all Form 4 activity", () => {
  render(<InsiderFlowCharts stats={[quarter(2026, 1, 10, 10)]} />);
  expect(screen.getByText(/all Form 4 activity/i)).toBeTruthy();
});

test("insider flow shows the acquired/disposed ratio trend", () => {
  render(<InsiderFlowCharts stats={[quarter(2026, 1, 10, 10)]} />);
  expect(screen.getByText(/ratio/i)).toBeTruthy();
});

test("insider flow shows an empty state without quarterly stats", () => {
  render(<InsiderFlowCharts stats={[]} />);
  expect(screen.getByText(/no quarterly insider statistics/i)).toBeTruthy();
});

test("insider flow tolerates the field being absent on older analyses", () => {
  render(<InsiderFlowCharts />);
  expect(screen.getByText(/no quarterly insider statistics/i)).toBeTruthy();
});

// --- Institutional ----------------------------------------------------------

const baseInstitutional: InstitutionalReport = {
  overall_institutional_signal: "neutral",
  confidence: "medium",
  narrative: "n/a",
  institutional_summary: {
    ownership_pct: 60,
    institutions_count: 100,
    insiders_pct: 1,
    top10_increasing: 6,
    top10_decreasing: 2,
    as_of: "2026-03-31",
  },
  notable_increases: [],
  notable_reductions: [],
  superinvestor_available: false,
  superinvestor_moves: [],
  superinvestor_read: "",
  concentration_assessment: "moderate",
};

test("institutional surfaces beneficial filings with filer, stake and date", () => {
  render(
    <InstitutionalFlowVisuals
      institutional={{
        ...baseInstitutional,
        beneficial_direction: "accumulating",
        beneficial_filings: [
          {
            filer: "Capital Research Global Investors",
            filing_date: "2026-06-04",
            shares: 75_279_354,
            pct_of_class: 11.1,
            filer_type: "IA",
            url: "https://sec.gov/x",
          },
        ],
      }}
    />,
  );
  expect(screen.getByText("Capital Research Global Investors")).toBeTruthy();
  expect(screen.getByText("2026-06-04")).toBeTruthy();
  expect(screen.getByText("11.10%")).toBeTruthy();
  expect(screen.getByText(/accumulating/i)).toBeTruthy();
});

test("institutional falls back to the cached 13F tally when no filings exist", () => {
  render(<InstitutionalFlowVisuals institutional={baseInstitutional} />);
  expect(screen.getByText(/cached 13F top-10/i)).toBeTruthy();
  expect(screen.getByText(/buying/i)).toBeTruthy();
});

test("institutional shows an empty state when neither source has data", () => {
  render(
    <InstitutionalFlowVisuals
      institutional={{
        ...baseInstitutional,
        institutional_summary: {
          ...baseInstitutional.institutional_summary,
          top10_increasing: 0,
          top10_decreasing: 0,
        },
      }}
    />,
  );
  expect(screen.getByText(/no institutional ownership filings/i)).toBeTruthy();
});

test("institutional reports distributing when 5%+ holders trim", () => {
  render(
    <InstitutionalFlowVisuals
      institutional={{
        ...baseInstitutional,
        beneficial_direction: "distributing",
        beneficial_filings: [
          { filer: "A", filing_date: "2026-06-01", shares: 10, pct_of_class: 4, filer_type: "HC", url: "" },
        ],
      }}
    />,
  );
  expect(screen.getByText(/distributing/i)).toBeTruthy();
});

// specs/028-dashboard-tweaks-batch US4 (FR-015, FR-016, FR-016a, FR-016b)
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test } from "vitest";
import type { CongressSummaryResponse } from "../../api/types";
import CongressSummary from "./CongressSummary";

afterEach(cleanup);

function summary(overrides: Partial<CongressSummaryResponse> = {}): CongressSummaryResponse {
  return {
    window_days: 90,
    most_bought: [{ ticker: "NVDA", buy_count: 7 }],
    high_dollar: [
      {
        trade_id: "t1", chamber: "senate", person_id: "B1", politician: "Jane Doe",
        district: "AR", owner: "Joint", ticker: "NVDA", asset_description: "Nvidia Corp",
        asset_type: "Stock", transaction_type: "Purchase",
        amount_range: "$250,001 - $500,000", transaction_date: "2026-06-01",
        disclosure_date: "2026-08-01", link: null,
      },
    ],
    high_dollar_threshold: "$100,001",
    as_of: "2026-08-22T09:00:00Z",
    ...overrides,
  };
}

function renderSummary(data: CongressSummaryResponse) {
  return render(
    <MemoryRouter>
      <CongressSummary data={data} />
    </MemoryRouter>,
  );
}

test("shows most-bought tickers with their counts", () => {
  renderSummary(summary());
  expect(screen.getAllByText("NVDA").length).toBeGreaterThan(0);
  expect(screen.getByText(/7 buys/)).toBeTruthy();
});

test("amounts render as the verbatim bracket string, never a computed number", () => {
  renderSummary(summary());
  expect(screen.getByText("$250,001 - $500,000")).toBeTruthy();
  expect(screen.queryByText(/375,000/)).toBeNull(); // no midpoint anywhere
});

test("an empty high_dollar array renders an explicit none-in-window message, not a hidden section", () => {
  renderSummary(summary({ high_dollar: [] }));
  expect(screen.getByText(/no.*high.dollar|none.*window/i)).toBeTruthy();
});

test("an empty most_bought array renders an explicit message", () => {
  renderSummary(summary({ most_bought: [] }));
  expect(screen.getByText(/no.*buying activity|no.*most.bought/i)).toBeTruthy();
});

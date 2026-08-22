// specs/029-company-profile-tweaks US5 (FR-027) — the Unclassified bucket.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../api/client";
import type { SectorSummary } from "../api/types";
import Sectors from "./Sectors";

vi.mock("../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function mockApi(sectors: SectorSummary[]) {
  (api.get as ReturnType<typeof vi.fn>).mockImplementation((url: string) => {
    if (url === "/sectors") return Promise.resolve({ data: sectors });
    if (url === "/sectors/etf-series") {
      return Promise.resolve({ data: { window: "6m", series: [], as_of: new Date().toISOString() } });
    }
    if (url === "/queue") {
      return Promise.resolve({ data: { pending: [], running: [], pending_count: 0, running_count: 0 } });
    }
    return Promise.resolve({ data: {} });
  });
}

function renderSectors() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/sectors"]}>
        <Routes>
          <Route path="/sectors" element={<Sectors />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function summary(overrides: Partial<SectorSummary>): SectorSummary {
  return {
    sector: "Technology",
    bullish_count: 1,
    bearish_count: 0,
    neutral_count: 0,
    ticker_count: 1,
    top_ticker: "AAPL",
    ...overrides,
  };
}

test("renders sectors returned by the API", async () => {
  mockApi([summary({ sector: "Technology" }), summary({ sector: "Financials", top_ticker: "JPM" })]);

  renderSectors();

  await waitFor(() => expect(screen.getAllByText("Technology").length).toBeGreaterThan(0));
  expect(screen.getAllByText("Financials").length).toBeGreaterThan(0);
});

test("the Unclassified bucket sorts last in both the row list and the card grid, despite having the highest bullish ratio", async () => {
  mockApi([
    summary({ sector: "Unclassified", bullish_count: 5, bearish_count: 0, ticker_count: 5, top_ticker: null }),
    summary({ sector: "Financials", bullish_count: 0, bearish_count: 1, ticker_count: 1, top_ticker: "JPM" }),
  ]);

  const { container } = renderSectors();

  await waitFor(() => expect(container.querySelectorAll("[data-sector-row]").length).toBe(2));

  const rows = Array.from(container.querySelectorAll("[data-sector-row]")).map((el) =>
    el.getAttribute("data-sector-row"),
  );
  expect(rows).toEqual(["Financials", "Unclassified"]);

  const cards = Array.from(container.querySelectorAll("[data-sector-card]")).map((el) =>
    el.getAttribute("data-sector-card"),
  );
  expect(cards).toEqual(["Financials", "Unclassified"]);
});

test("the Unclassified bucket reads as awaiting a pull, not a real sector", async () => {
  mockApi([summary({ sector: "Unclassified", bullish_count: 0, bearish_count: 0, neutral_count: 0, ticker_count: 2, top_ticker: null })]);

  renderSectors();

  await waitFor(() => expect(screen.getAllByText("Unclassified").length).toBeGreaterThan(0));
  expect(screen.getAllByText(/awaiting their next analysis pull/i).length).toBeGreaterThan(0);
});

test("shows the existing empty state when there are no sectors at all", async () => {
  mockApi([]);

  renderSectors();

  await waitFor(() => expect(screen.getByText("No sector data yet")).toBeTruthy());
});

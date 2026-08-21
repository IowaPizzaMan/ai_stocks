import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../api/client";
import type { EarningsCalendarEntry, EarningsCalendarResponse } from "../api/types";
import EarningsScan from "./EarningsScan";

vi.mock("../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function entry(overrides: Partial<EarningsCalendarEntry> = {}): EarningsCalendarEntry {
  return {
    ticker: "AAA",
    company: "AAA Co",
    sector: "Technology",
    market_cap: 10e9,
    report_date: "2026-08-17",
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

function renderPage(initialPath = "/earnings") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialPath]}>
        <EarningsScan />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("loads and renders rows automatically on arrival — no button required", async () => {
  const response: EarningsCalendarResponse = {
    entries: [entry({ ticker: "TJX" })],
    total_before_screen: 1,
    stale: false,
    fetched_at: "2026-08-17T12:00:00Z",
  };
  vi.mocked(api.get).mockResolvedValue({ data: response });

  renderPage();

  expect(screen.queryByRole("button", { name: /scan/i })).toBeNull();
  await waitFor(() => expect(screen.getByText("TJX")).toBeTruthy());
  expect(api.get).toHaveBeenCalledWith(expect.stringContaining("/earnings/calendar?from="));
});

test("renders a staleness banner when the response is served from stale cache", async () => {
  const response: EarningsCalendarResponse = {
    entries: [entry()],
    total_before_screen: 1,
    stale: true,
    fetched_at: "2026-08-17T09:00:00Z",
  };
  vi.mocked(api.get).mockResolvedValue({ data: response });

  renderPage();

  await waitFor(() => expect(screen.getByText(/cached data/i)).toBeTruthy());
});

test("renders an explicit error state on request failure, never a bare empty table", async () => {
  vi.mocked(api.get).mockRejectedValue(new Error("network down"));

  renderPage();

  await waitFor(() => expect(screen.getByText(/couldn't load the earnings calendar/i)).toBeTruthy());
});

test("empty window shows a date-focused empty state, not a bare table", async () => {
  const response: EarningsCalendarResponse = {
    entries: [], total_before_screen: 0, stale: false, fetched_at: "2026-08-17T12:00:00Z",
  };
  vi.mocked(api.get).mockResolvedValue({ data: response });

  renderPage();

  await waitFor(() => expect(screen.getByText(/no companies report in this window/i)).toBeTruthy());
});

test("big-movers toggle emptying the table says the toggle is the cause", async () => {
  const response: EarningsCalendarResponse = {
    entries: [entry({ reporting_state: "upcoming" })], // no surprise to measure
    total_before_screen: 1, stale: false, fetched_at: "2026-08-17T12:00:00Z",
  };
  vi.mocked(api.get).mockResolvedValue({ data: response });

  renderPage("/earnings?movers=1");

  await waitFor(() => expect(screen.getByText(/"big movers only" is hiding/i)).toBeTruthy());
});

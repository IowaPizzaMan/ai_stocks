// Stocks page ↔ market news panel integration — specs/022-market-news-feed.
// Kept in its own file from Stocks.test.tsx (which covers the grid) so the two
// concerns don't fight over one module's mocks.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../api/client";
import Stocks from "./Stocks";

vi.mock("../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const NEWS = {
  articles: [
    {
      ticker: "NBIS",
      datetime: "2026-08-16 20:13:00",
      date: "2026-08-16",
      source: "Seeking Alpha",
      headline: "Nebius momentum has staying power",
      url: "https://example.com/nbis",
      text_excerpt: "…",
    },
  ],
  as_of: "2026-08-16T20:15:00+00:00",
  stale: false,
};

const FEED = {
  items: [
    {
      ticker: "AAPL",
      timestamp: "2026-08-15T12:00:00Z",
      signal: "bullish",
      conviction: "high",
      summary: "Holding support.",
      key_trends: [],
      flags: [],
    },
  ],
  total: 1,
  page: 1,
  page_size: 60,
};

/** Records every URL + params pair the page requests. */
function mockApi({ newsFails = false } = {}) {
  const calls: { url: string; params?: Record<string, unknown> }[] = [];
  (api.get as ReturnType<typeof vi.fn>).mockImplementation(
    (url: string, config?: { params?: Record<string, unknown> }) => {
      calls.push({ url, params: config?.params });
      if (url.includes("/market/news")) {
        return newsFails ? Promise.reject(new Error("boom")) : Promise.resolve({ data: NEWS });
      }
      if (url.includes("/analysis/feed")) return Promise.resolve({ data: FEED });
      return Promise.resolve({ data: {} });
    },
  );
  return calls;
}

function renderStocks(search = "") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/${search}`]}>
        <Routes>
          <Route path="/" element={<Stocks />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// --- US1: placement ---------------------------------------------------------

test("renders the market news panel below the analysis grid", async () => {
  mockApi();
  const { container } = renderStocks();

  // the panel's heading shows during loading too, so wait for real content
  await waitFor(() => expect(screen.getByText("Nebius momentum has staying power")).toBeTruthy());
  await waitFor(() => expect(screen.getByText("Bullish")).toBeTruthy());

  const html = container.innerHTML;
  // the grid's signal heading must appear before the news section
  expect(html.indexOf("Bullish")).toBeLessThan(html.indexOf("Market News"));
});

// --- US1: filter independence (FR-001b) -------------------------------------

test("grid filters do not change the news request or its articles", async () => {
  const calls = mockApi();
  renderStocks("?sector=Technology&signal=bullish&ticker=AAPL");

  await waitFor(() => expect(screen.getByText("Nebius momentum has staying power")).toBeTruthy());

  // the feed request carries the filters…
  const feedCall = calls.find((c) => c.url.includes("/analysis/feed"));
  expect(feedCall?.params).toMatchObject({ sector: "Technology", signal: "bullish", ticker: "AAPL" });

  // …the news request carries none of them
  const newsCalls = calls.filter((c) => c.url.includes("/market/news"));
  expect(newsCalls).toHaveLength(1);
  expect(newsCalls[0].url).toBe("/market/news");
  expect(newsCalls[0].params).toBeUndefined();

  // and the same articles render regardless
  expect(screen.getByText("Nebius momentum has staying power")).toBeTruthy();
});

test("the news panel renders identically with and without filters", async () => {
  mockApi();
  const { unmount } = renderStocks();
  const target = "Nebius momentum has staying power";
  await waitFor(() => expect(screen.getByText(target)).toBeTruthy());
  const unfiltered = screen.getByText(target).textContent;
  unmount();

  mockApi();
  renderStocks("?sector=Healthcare&conviction=low");
  await waitFor(() => expect(screen.getByText(target)).toBeTruthy());
  expect(screen.getByText(target).textContent).toBe(unfiltered);
});

// --- US3: a news failure must not degrade the grid (FR-012) -----------------

test("the analysis grid still renders when the news request fails", async () => {
  mockApi({ newsFails: true });
  renderStocks();

  await waitFor(() => expect(screen.getByText(/market news is unavailable/i)).toBeTruthy());

  // grid content is intact
  expect(screen.getByText("Bullish")).toBeTruthy();
  expect(screen.getByText("AAPL")).toBeTruthy();
});

// Stocks page ↔ market news panel integration — specs/022-market-news-feed,
// relocated behind the News tab by specs/027-stocks-news-tab-ai-summary
// (FR-002: content/behavior unchanged by the move, only its location did).
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

const EMPTY_DIGEST = {
  as_of: null, overview: null, highlights: [], stock_count: 0, total_tracked_count: 0,
  capped: false, stale: false,
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
      if (url.includes("/portfolio/digest")) return Promise.resolve({ data: EMPTY_DIGEST });
      return Promise.resolve({ data: {} });
    },
  );
  return calls;
}

function renderStocks(searchAndHash = "") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/${searchAndHash}`]}>
        <Routes>
          <Route path="/" element={<Stocks />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// --- US1 (spec 027): the panel now lives on its own News tab -----------------

test("the market news panel appears on the News tab, not the default grid tab", async () => {
  mockApi();
  renderStocks();

  await waitFor(() => expect(screen.getByText("AAPL")).toBeTruthy());
  expect(screen.queryByText("Nebius momentum has staying power")).toBeNull();
});

test("the grid tab never requests market news at all — it isn't mounted there", async () => {
  const calls = mockApi();
  renderStocks();

  await waitFor(() => expect(screen.getByText("AAPL")).toBeTruthy());
  expect(calls.some((c) => c.url.includes("/market/news"))).toBe(false);
});

// --- US1: filter independence (FR-001b, unchanged by the relocation) --------

test("grid filters do not change the news request or its articles", async () => {
  const calls = mockApi();
  renderStocks("?sector=Technology&signal=bullish&ticker=AAPL#news");

  await waitFor(() => expect(screen.getByText("Nebius momentum has staying power")).toBeTruthy());

  // the feed request (still made in the background) carries the filters…
  const feedCall = calls.find((c) => c.url.includes("/analysis/feed"));
  expect(feedCall?.params).toMatchObject({ sector: "Technology", signal: "bullish", ticker: "AAPL" });

  // …the news request carries none of them
  const newsCalls = calls.filter((c) => c.url.includes("/market/news"));
  expect(newsCalls).toHaveLength(1);
  expect(newsCalls[0].url).toBe("/market/news");
  expect(newsCalls[0].params).toBeUndefined();

  expect(screen.getByText("Nebius momentum has staying power")).toBeTruthy();
});

test("the news panel renders identically with and without filters", async () => {
  mockApi();
  const { unmount } = renderStocks("#news");
  const target = "Nebius momentum has staying power";
  await waitFor(() => expect(screen.getByText(target)).toBeTruthy());
  const unfiltered = screen.getByText(target).textContent;
  unmount();

  mockApi();
  renderStocks("?sector=Healthcare&conviction=low#news");
  await waitFor(() => expect(screen.getByText(target)).toBeTruthy());
  expect(screen.getByText(target).textContent).toBe(unfiltered);
});

// --- US3 (spec 022): a news failure degrades gracefully, confined to its tab -

test("a market news failure shows a graceful message on the News tab, never an error page", async () => {
  mockApi({ newsFails: true });
  renderStocks("#news");

  await waitFor(() => expect(screen.getByText(/market news is unavailable/i)).toBeTruthy());
});

test("a market news failure has no effect on the grid tab, which never requested it", async () => {
  mockApi({ newsFails: true });
  renderStocks();

  await waitFor(() => expect(screen.getByText("Bullish")).toBeTruthy());
  expect(screen.getByText("AAPL")).toBeTruthy();
  expect(screen.queryByText(/market news is unavailable/i)).toBeNull();
});

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../api/client";
import type { AnalysisFeedItem, FeedResponse, MarketFlowEvent } from "../api/types";
import Stocks from "./Stocks";

vi.mock("../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function feedItem(overrides: Partial<AnalysisFeedItem>): AnalysisFeedItem {
  return {
    ticker: "AAA",
    timestamp: new Date().toISOString(),
    signal: "neutral",
    conviction: "medium",
    summary: "Summary.",
    key_trends: [],
    flags: [],
    ...overrides,
  } as AnalysisFeedItem;
}

function flowEvent(overrides: Partial<MarketFlowEvent> = {}): MarketFlowEvent {
  return {
    event_id: "evt-1",
    category: "market_flow",
    kind: "breadth_divergence",
    divergence_type: "bullish",
    headline: "Breadth divergence detected",
    body: "NYMO diverging from price.",
    price_points: [],
    osc_points: [],
    nymo_current: 12,
    detected_on: new Date().toISOString(),
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

function mockApi({
  items = [],
  total,
  feedError = false,
  flowEvents = [],
}: {
  items?: AnalysisFeedItem[];
  total?: number;
  feedError?: boolean;
  flowEvents?: MarketFlowEvent[];
} = {}) {
  // Mirrors the backend's server-side filtering (ticker: substring, others: exact match)
  // so tests can verify the Stocks page forwards URL filters into the request and renders
  // whatever the (simulated) filtered response contains.
  vi.mocked(api.get).mockImplementation(async (url: string, config?: unknown) => {
    if (url === "/analysis/feed") {
      if (feedError) throw new Error("network down");
      const params = (config as { params?: Record<string, unknown> } | undefined)?.params ?? {};
      const filtered = items.filter((item) => {
        if (params.signal && item.signal !== params.signal) return false;
        if (params.sector && item.sector !== params.sector) return false;
        if (params.conviction && item.conviction !== params.conviction) return false;
        if (
          params.ticker &&
          !item.ticker.toLowerCase().includes(String(params.ticker).toLowerCase())
        )
          return false;
        return true;
      });
      const body: FeedResponse = {
        items: filtered,
        total: total ?? filtered.length,
        page: 1,
        page_size: 60,
      };
      return { data: body };
    }
    // The Stocks page no longer reads breadth/flow-events (moved to the Macro
    // page) — these branches only exist so an accidental call doesn't throw.
    if (url === "/market/flow-events") return { data: flowEvents };
    if (url === "/market/breadth") return { data: null };
    if (url === "/queue") return { data: { pending_count: 0, running_count: 0 } };
    throw new Error(`unexpected GET ${url}`);
  });
}

function renderStocks(initialEntries: string[] = ["/"]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>
        <Stocks />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// Navigation assertions need a real destination route to land on, rather than
// just Stocks in isolation.
function renderStocksWithRouting() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<Stocks />} />
          <Route path="/stock/:ticker" element={<div>STOCK DETAIL PAGE</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("renders tiles grouped under labeled dividers in bullish, neutral, bearish order", async () => {
  mockApi({
    items: [
      feedItem({ ticker: "BEAR1", signal: "bearish" }),
      feedItem({ ticker: "BULL1", signal: "bullish" }),
      feedItem({ ticker: "NEUT1", signal: "neutral" }),
    ],
  });

  renderStocks();

  await waitFor(() => expect(screen.getByText("BULL1")).toBeDefined());

  const headings = screen.getAllByRole("heading", { name: /^(bullish|neutral|bearish)$/i });
  expect(headings.map((h) => h.textContent?.toLowerCase())).toEqual([
    "bullish",
    "neutral",
    "bearish",
  ]);
});

test("shows a board of skeleton tiles during initial load, then swaps to real tiles", async () => {
  mockApi({ items: [feedItem({ ticker: "AAA" })] });

  const { container } = renderStocks();

  expect(container.querySelectorAll('[data-skeleton-tile="true"]').length).toBeGreaterThanOrEqual(20);

  await waitFor(() => expect(screen.getByText("AAA")).toBeDefined());

  expect(container.querySelectorAll('[data-skeleton-tile="true"]')).toHaveLength(0);
});

test("shows the existing error message when the feed fetch fails", async () => {
  mockApi({ feedError: true });

  renderStocks();

  await waitFor(() => expect(screen.getByText(/couldn't reach the api/i)).toBeDefined());
});

test("shows the existing empty state when there are no analyses", async () => {
  mockApi({ items: [] });

  renderStocks();

  await waitFor(() => expect(screen.getByText("No analyses yet")).toBeDefined());
});

test("clicking a tile navigates to that stock's detail page", async () => {
  mockApi({ items: [feedItem({ ticker: "BULL1", signal: "bullish" })] });

  renderStocksWithRouting();

  const tile = await screen.findByRole("button", { name: /BULL1/i });
  fireEvent.click(tile);

  expect(await screen.findByText("STOCK DETAIL PAGE")).toBeDefined();
});

test("focusing a tile surfaces its hover/focus preview", async () => {
  mockApi({ items: [feedItem({ ticker: "BULL1", signal: "bullish", summary: "A bullish thesis." })] });

  renderStocks();

  const tile = await screen.findByRole("button", { name: /BULL1/i });
  expect(screen.queryByRole("tooltip")).toBeNull();

  fireEvent.focus(tile);

  expect(await screen.findByText("A bullish thesis.")).toBeDefined();
  expect(screen.getByRole("tooltip")).toBeDefined();
});

test("narrows the board to matching tiles when a signal filter is applied via the URL", async () => {
  mockApi({
    items: [
      feedItem({ ticker: "BULL1", signal: "bullish" }),
      feedItem({ ticker: "BEAR1", signal: "bearish" }),
    ],
  });

  renderStocks(["/?signal=bearish"]);

  await waitFor(() => expect(screen.getByText("BEAR1")).toBeDefined());
  expect(screen.queryByText("BULL1")).toBeNull();
});

test("restores the full board when filters are cleared", async () => {
  mockApi({
    items: [
      feedItem({ ticker: "BULL1", signal: "bullish" }),
      feedItem({ ticker: "BEAR1", signal: "bearish" }),
    ],
  });

  renderStocks(["/"]);

  await waitFor(() => expect(screen.getByText("BULL1")).toBeDefined());
  expect(screen.getByText("BEAR1")).toBeDefined();
});

test("never renders pinned market-flow cards, even when flow events exist", async () => {
  mockApi({
    items: [feedItem({ ticker: "AAA" })],
    flowEvents: [flowEvent({ headline: "Breadth divergence detected" })],
  });

  renderStocks(["/"]);

  await waitFor(() => expect(screen.getByText("AAA")).toBeDefined());
  expect(screen.queryByText("Breadth divergence detected")).toBeNull();
  expect(screen.queryByText("market flow")).toBeNull();
});

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../api/client";
import type {
  AnalysisFeedItem,
  FeedResponse,
  MarketFlowEvent,
  MarketNewsArticle,
  PortfolioDigestResponse,
} from "../api/types";
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

function newsArticle(overrides: Partial<MarketNewsArticle> = {}): MarketNewsArticle {
  return {
    ticker: "AAA",
    datetime: "2026-08-21 12:00:00",
    date: "2026-08-21",
    source: "Wire",
    headline: "Some market headline",
    url: "https://example.com/article",
    text_excerpt: "excerpt",
    ...overrides,
  };
}

const EMPTY_DIGEST: PortfolioDigestResponse = {
  as_of: null,
  overview: null,
  highlights: [],
  stock_count: 0,
  total_tracked_count: 0,
  capped: false,
  stale: false,
};

function mockApi({
  items = [],
  total,
  feedError = false,
  flowEvents = [],
  newsArticles = [],
  pageSize = 60,
  digest = EMPTY_DIGEST,
}: {
  items?: AnalysisFeedItem[];
  total?: number;
  feedError?: boolean;
  flowEvents?: MarketFlowEvent[];
  newsArticles?: MarketNewsArticle[];
  pageSize?: number;
  digest?: PortfolioDigestResponse;
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
      const page = Number(params.page ?? 1);
      const pageItems = filtered.slice((page - 1) * pageSize, page * pageSize);
      const body: FeedResponse = {
        items: pageItems,
        total: total ?? filtered.length,
        page,
        page_size: pageSize,
      };
      return { data: body };
    }
    // The Stocks page no longer reads breadth/flow-events (moved to the Macro
    // page) — these branches only exist so an accidental call doesn't throw.
    if (url === "/market/flow-events") return { data: flowEvents };
    if (url === "/market/breadth") return { data: null };
    if (url === "/market/news") return { data: { articles: newsArticles, as_of: null, stale: false } };
    if (url === "/portfolio/digest") return { data: digest };
    if (url === "/queue") return { data: { pending: [], running: [], pending_count: 0, running_count: 0 } };
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

  // Anchored to the tile's own aria-label prefix — the per-tile delete
  // control (specs/023-remove-stocks) also has "BULL1" in its accessible
  // name ("Delete BULL1 and its data"), so an unanchored match is ambiguous.
  const tile = await screen.findByRole("button", { name: /^BULL1/i });
  fireEvent.click(tile);

  expect(await screen.findByText("STOCK DETAIL PAGE")).toBeDefined();
});

test("focusing a tile surfaces its hover/focus preview", async () => {
  mockApi({ items: [feedItem({ ticker: "BULL1", signal: "bullish", summary: "A bullish thesis." })] });

  renderStocks();

  // Anchored to the tile's own aria-label prefix — the per-tile delete
  // control (specs/023-remove-stocks) also has "BULL1" in its accessible
  // name ("Delete BULL1 and its data"), so an unanchored match is ambiguous.
  const tile = await screen.findByRole("button", { name: /^BULL1/i });
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

// --- US1: dedicated News tab -------------------------------------------------

test("the default tab shows the filter bar and grid, not the market news list", async () => {
  mockApi({
    items: [feedItem({ ticker: "AAA" })],
    newsArticles: [newsArticle({ headline: "Relocated headline" })],
  });

  renderStocks();

  await waitFor(() => expect(screen.getByText("AAA")).toBeDefined());
  expect(screen.queryByText("Relocated headline")).toBeNull();
  expect(screen.queryByText("Market News")).toBeNull();
});

test("the #news tab shows the relocated market news list, not the grid", async () => {
  mockApi({
    items: [feedItem({ ticker: "AAA" })],
    newsArticles: [newsArticle({ ticker: "ZZZ", headline: "Relocated headline" })],
  });

  renderStocks(["/#news"]);

  await waitFor(() => expect(screen.getByText("Relocated headline")).toBeDefined());
  expect(screen.queryByRole("button", { name: /^AAA/i })).toBeNull();
});

test("an unrecognized tab hash falls back to the default grid tab", async () => {
  mockApi({ items: [feedItem({ ticker: "AAA" })] });

  renderStocks(["/#bogus-tab"]);

  await waitFor(() => expect(screen.getByText("AAA")).toBeDefined());
  expect(screen.queryByText("Market News")).toBeNull();
});

// --- US2: bounded grid, no auto-scroll fetching ------------------------------

test("does not fetch a further page automatically — only via the Load more control", async () => {
  mockApi({
    items: [feedItem({ ticker: "AAA" }), feedItem({ ticker: "BBB" })],
    total: 2,
    pageSize: 1, // forces a second page to exist without needing 60 fixtures
  });

  renderStocks();

  const loadMore = await screen.findByRole("button", { name: /load more/i });
  expect(loadMore).toBeDefined();
  // Only the initial page request should have fired — mounting/rendering alone
  // (no IntersectionObserver, no scroll simulation) must not trigger a second.
  const feedCalls = vi.mocked(api.get).mock.calls.filter(([url]) => url === "/analysis/feed");
  expect(feedCalls.length).toBe(1);

  fireEvent.click(loadMore);

  await waitFor(() => {
    const calls = vi.mocked(api.get).mock.calls.filter(([url]) => url === "/analysis/feed");
    expect(calls.length).toBe(2);
  });
});

test("no Load more control renders once every analysis has loaded", async () => {
  mockApi({ items: [feedItem({ ticker: "AAA" })], total: 1 });

  renderStocks();

  await waitFor(() => expect(screen.getByText("AAA")).toBeDefined());
  expect(screen.queryByRole("button", { name: /load more/i })).toBeNull();
});

// --- US3: cross-stock AI summary panel is filter-independent ----------------

test("the portfolio summary panel is unchanged when a grid filter is applied", async () => {
  const digest: PortfolioDigestResponse = {
    as_of: "2026-08-21T18:00:00Z",
    overview: "Momentum skews bullish across the tracked set.",
    highlights: [],
    stock_count: 3,
    total_tracked_count: 3,
    capped: false,
    stale: false,
  };
  mockApi({
    items: [
      feedItem({ ticker: "BULL1", signal: "bullish" }),
      feedItem({ ticker: "BEAR1", signal: "bearish" }),
    ],
    digest,
  });

  renderStocks(["/?signal=bearish"]);

  await waitFor(() => expect(screen.getByText("BEAR1")).toBeDefined());
  expect(screen.getByText(/momentum skews/i)).toBeDefined();

  const digestCalls = vi.mocked(api.get).mock.calls.filter(([url]) => url === "/portfolio/digest");
  expect(digestCalls.length).toBe(1); // one request regardless of the filter
});

test("the grid tab's content sits in its own scrollable region, not the page body", async () => {
  mockApi({ items: [feedItem({ ticker: "AAA" })] });

  const { container } = renderStocks();

  await waitFor(() => expect(screen.getByText("AAA")).toBeDefined());
  const scrollRegion = container.querySelector('[data-scroll-region="true"]');
  expect(scrollRegion).not.toBeNull();
  expect(scrollRegion?.contains(screen.getByText("AAA"))).toBe(true);
  // The filter bar/tab bar are siblings of the scroll region, not inside it —
  // so they stay on screen while only the region below them scrolls.
  const tabBarNav = document.querySelector("nav");
  expect(scrollRegion?.contains(tabBarNav)).toBe(false);
});

// spec 027 FR-007b (clarified 2026-08-22): the digest panel renders beside the
// grid as a second column, not stacked above it.
test("the grid and the portfolio summary panel render as two side-by-side columns, grid first", async () => {
  mockApi({ items: [feedItem({ ticker: "AAA" })] });

  const { container } = renderStocks();

  await waitFor(() => expect(screen.getByText("AAA")).toBeDefined());

  const gridColumn = container.querySelector('[data-grid-column="true"]');
  const digestColumn = container.querySelector('[data-digest-column="true"]');
  expect(gridColumn).not.toBeNull();
  expect(digestColumn).not.toBeNull();
  expect(gridColumn?.contains(screen.getByText("AAA"))).toBe(true);
  expect(digestColumn?.textContent).toMatch(/portfolio summary/i);

  // Siblings of one row wrapper, grid column preceding the digest column.
  expect(gridColumn?.parentElement).toBe(digestColumn?.parentElement);
  expect(
    gridColumn!.compareDocumentPosition(digestColumn!) & Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy();
});

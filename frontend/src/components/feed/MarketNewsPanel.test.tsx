import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../../api/client";
import type { MarketNewsArticle, MarketNewsResponse } from "../../api/types";
import { useMarketNews } from "../../hooks/useMarketNews";
import MarketNewsPanel from "./MarketNewsPanel";

vi.mock("../../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const article = (i: number, overrides: Partial<MarketNewsArticle> = {}): MarketNewsArticle => ({
  ticker: "AAPL",
  datetime: `2026-08-16 ${String(23 - (i % 24)).padStart(2, "0")}:30:00`,
  date: "2026-08-16",
  source: "Seeking Alpha",
  headline: `Story number ${i}`,
  url: `https://example.com/${i}`,
  text_excerpt: "excerpt",
  ...overrides,
});

function renderPanel(body: Partial<MarketNewsResponse> = {}, opts: { fail?: boolean } = {}) {
  (api.get as ReturnType<typeof vi.fn>).mockImplementation(() =>
    opts.fail
      ? Promise.reject(new Error("boom"))
      : Promise.resolve({
          data: { articles: [article(0)], as_of: "2026-08-16T20:00:00+00:00", stale: false, ...body },
        }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <MarketNewsPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// --- US1: rows, cap, links --------------------------------------------------

test("renders a row per article with time, source, ticker and headline", async () => {
  renderPanel({ articles: [article(1, { ticker: "NBIS", source: "Barrons" })] });
  await waitFor(() => expect(screen.getByText("Story number 1")).toBeTruthy());
  expect(screen.getByText("Barrons")).toBeTruthy();
  expect(screen.getByText("NBIS")).toBeTruthy();
  // the row carries a clock time; the "as of" note above carries only a date
  expect(screen.getByText(/22:30/)).toBeTruthy();
});

test("renders every article the endpoint returns, up to 20", async () => {
  const articles = Array.from({ length: 20 }, (_, i) => article(i));
  const { container } = renderPanel({ articles });
  await waitFor(() => expect(screen.getByText("Story number 0")).toBeTruthy());
  expect(container.querySelectorAll("li")).toHaveLength(20);
  expect(screen.getByText("Story number 19")).toBeTruthy();
});

test("has no load-more control — the list simply ends", async () => {
  renderPanel({ articles: Array.from({ length: 20 }, (_, i) => article(i)) });
  await waitFor(() => expect(screen.getByText("Story number 0")).toBeTruthy());
  expect(screen.queryByRole("button", { name: /more|load/i })).toBeNull();
});

test("a null ticker renders without a badge", async () => {
  renderPanel({ articles: [article(2, { ticker: null, headline: "Fed commentary" })] });
  await waitFor(() => expect(screen.getByText("Fed commentary")).toBeTruthy());
  expect(screen.queryByText("AAPL")).toBeNull();
});

test("headlines open in a new tab and tickers link to the stock page", async () => {
  const { container } = renderPanel({ articles: [article(3, { ticker: "MSFT" })] });
  await waitFor(() => expect(screen.getByText("Story number 3")).toBeTruthy());

  const headline = screen.getByText("Story number 3") as HTMLAnchorElement;
  expect(headline.getAttribute("target")).toBe("_blank");
  expect(headline.getAttribute("rel")).toBe("noreferrer");
  expect(headline.getAttribute("href")).toBe("https://example.com/3");

  const ticker = container.querySelector('a[href="/stocks/MSFT"]');
  expect(ticker).toBeTruthy();
});

// --- US2: no polling --------------------------------------------------------

test("the query uses a 60-minute staleTime and never polls", () => {
  // Asserted on the hook's own options so a future edit can't silently add polling.
  const client = new QueryClient();
  let observed: { staleTime?: number; refetchInterval?: unknown } = {};
  function Probe() {
    useMarketNews();
    observed = (client.getQueryCache().find({ queryKey: ["market-news"] })?.options ??
      {}) as typeof observed;
    return null;
  }
  (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
    data: { articles: [], as_of: null, stale: false },
  });
  render(
    <QueryClientProvider client={client}>
      <Probe />
    </QueryClientProvider>,
  );
  expect(observed.staleTime).toBe(60 * 60 * 1000);
  expect(observed.refetchInterval).toBeUndefined();
});

// --- US3: loading, error, empty, stale --------------------------------------

test("shows a loading state before the request resolves", () => {
  renderPanel();
  expect(screen.getByText(/loading market news/i)).toBeTruthy();
});

test("shows a brief unavailable message when the request fails", async () => {
  renderPanel({}, { fail: true });
  await waitFor(() => expect(screen.getByText(/market news is unavailable/i)).toBeTruthy());
});

test("shows an empty state when no articles come back", async () => {
  renderPanel({ articles: [] });
  await waitFor(() => expect(screen.getByText(/no recent market news/i)).toBeTruthy());
});

test("labels the list as not current when the response is stale", async () => {
  renderPanel({ articles: [article(4)], stale: true });
  await waitFor(() => expect(screen.getByText("Story number 4")).toBeTruthy());
  expect(screen.getByText(/not current/i)).toBeTruthy();
});

test("shows the as-of date when the response is fresh", async () => {
  renderPanel({ articles: [article(5)], stale: false });
  await waitFor(() => expect(screen.getByText("Story number 5")).toBeTruthy());
  expect(screen.getByText(/as of/i)).toBeTruthy();
});

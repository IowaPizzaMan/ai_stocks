// Market news page — specs/022-market-news-feed (original panel), promoted
// from a tab nested inside the Stocks page to its own top-level route by
// specs/029-company-profile-tweaks US1 (FR-002: content/behavior unchanged
// by the move, only its location did — this file replaces
// Stocks.market-news.test.tsx, which tested the same panel while it lived
// inside Stocks.tsx).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../api/client";
import News from "./News";

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

function mockApi({ newsFails = false } = {}) {
  const calls: { url: string; params?: Record<string, unknown> }[] = [];
  (api.get as ReturnType<typeof vi.fn>).mockImplementation(
    (url: string, config?: { params?: Record<string, unknown> }) => {
      calls.push({ url, params: config?.params });
      if (url.includes("/market/news")) {
        return newsFails ? Promise.reject(new Error("boom")) : Promise.resolve({ data: NEWS });
      }
      return Promise.resolve({ data: {} });
    },
  );
  return calls;
}

function renderNews() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/news"]}>
        <News />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("the News page shows the market news panel content", async () => {
  mockApi();
  renderNews();

  await waitFor(() => expect(screen.getByText("Nebius momentum has staying power")).toBeTruthy());
});

test("the News page requests /market/news with no extra params", async () => {
  const calls = mockApi();
  renderNews();

  await waitFor(() => expect(screen.getByText("Nebius momentum has staying power")).toBeTruthy());

  const newsCalls = calls.filter((c) => c.url.includes("/market/news"));
  expect(newsCalls).toHaveLength(1);
  expect(newsCalls[0].url).toBe("/market/news");
  expect(newsCalls[0].params).toBeUndefined();
});

test("a market news failure shows a graceful message, never an error page", async () => {
  mockApi({ newsFails: true });
  renderNews();

  await waitFor(() => expect(screen.getByText(/market news is unavailable/i)).toBeTruthy());
});

// News page — specs/022-market-news-feed (original panel) promoted to a
// top-level route by specs/029-company-profile-tweaks US1, then superseded
// by the mixed general/stock/FMP-article stream in specs/035-chat-and-news-upgrade
// US2 (FR-005, FR-006): MarketNewsPanel (/market/news, stock-latest only) is
// replaced by NewsFeed (/news, all three source types interleaved).
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

const MIXED_NEWS = {
  articles: [
    {
      url: "https://example.com/general",
      source_type: "general",
      title: "Ukraine is targeting Russia's retail giants",
      published_at: "2026-08-25T06:20:17+00:00",
      published_date: "2026-08-25",
      publisher: "CNBC",
      site: "cnbc.com",
      author: null,
      body_html: null,
      body_text: "Ukraine's drone campaign is expanding...",
      image_url: null,
      tickers: [],
    },
    {
      url: "https://example.com/fmp-article",
      source_type: "fmp_article",
      title: "Extra Space Storage (NYSE:EXR): Analyst Ratings",
      published_at: "2026-08-24T21:00:21+00:00",
      published_date: "2026-08-24",
      publisher: "Tony Dante",
      site: "Financial Modeling Prep",
      author: "Tony Dante",
      body_html: "<ul><li>Most analysts maintain a <strong>Hold</strong> rating</li></ul>",
      body_text: "Most analysts maintain a Hold rating",
      image_url: null,
      tickers: ["EXR"],
    },
  ],
  total: 2,
  as_of: "2026-08-25T14:00:00+00:00",
};

function mockApi({ newsFails = false } = {}) {
  const calls: { url: string; params?: Record<string, unknown> }[] = [];
  (api.get as ReturnType<typeof vi.fn>).mockImplementation(
    (url: string, config?: { params?: Record<string, unknown> }) => {
      calls.push({ url, params: config?.params });
      if (url === "/news") {
        return newsFails ? Promise.reject(new Error("boom")) : Promise.resolve({ data: MIXED_NEWS });
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

test("the News page shows stories from more than one source type interleaved", async () => {
  mockApi();
  renderNews();

  await waitFor(() =>
    expect(screen.getByText("Ukraine is targeting Russia's retail giants")).toBeTruthy(),
  );
  expect(screen.getByText(/Extra Space Storage/)).toBeTruthy();
  expect(screen.getByText("Market")).toBeTruthy(); // general's type badge
  expect(screen.getByText("Analysis")).toBeTruthy(); // fmp_article's type badge
});

test("the News page requests /news with no extra params", async () => {
  const calls = mockApi();
  renderNews();

  await waitFor(() =>
    expect(screen.getByText("Ukraine is targeting Russia's retail giants")).toBeTruthy(),
  );

  const newsCalls = calls.filter((c) => c.url === "/news");
  expect(newsCalls).toHaveLength(1);
});

test("a news fetch failure shows a graceful message, never an error page", async () => {
  mockApi({ newsFails: true });
  renderNews();

  await waitFor(() => expect(screen.getByText(/news is unavailable/i)).toBeTruthy());
});

test("an FMP article's HTML formatting renders instead of raw tag text", async () => {
  mockApi();
  renderNews();

  await waitFor(() => expect(screen.getByText(/Extra Space Storage/)).toBeTruthy());
  // The <strong>Hold</strong> should render as an actual <strong> element,
  // not the literal string "<strong>Hold</strong>" (FR-006a).
  const hold = screen.getByText("Hold");
  expect(hold.tagName.toLowerCase()).toBe("strong");
});

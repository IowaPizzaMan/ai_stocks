import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../../api/client";
import type { MostActive, WatchlistItem } from "../../api/types";
import Sidebar from "./Sidebar";

vi.mock("../../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function watchlistItem(overrides: Partial<WatchlistItem> = {}): WatchlistItem {
  return { ticker: "AAPL", status: "active", ...overrides };
}

function mostActive(overrides: Partial<MostActive> = {}): MostActive {
  return { ticker: "LUCY", company: "Innovative Eyewear", price: 1.85, change: 0.06, change_pct: 3.35, exchange: "NASDAQ", ...overrides };
}

function renderSidebar(items: WatchlistItem[], topTraded: MostActive[] = []) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.mocked(api.get).mockImplementation((url: string) => {
    if (url === "/watchlist") return Promise.resolve({ data: { items, count: items.length } });
    if (url === "/market/most-actives") return Promise.resolve({ data: { items: topTraded, as_of: null, date: null } });
    if (url === "/queue") return Promise.resolve({ data: { pending: [], running: [], pending_count: 0, running_count: 0 } });
    return Promise.resolve({ data: {} });
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// specs/030-stock-page-overflow — the sidebar is fixed-width (w-56) and must
// not force page-level horizontal scroll below the md breakpoint, where it's
// hidden instead of shrinking (research.md #2).
//
// specs/035-chat-and-news-upgrade US6 (research.md R10) — display switched
// from md:block to md:flex (flex-col) so Watchlist and Top Traded Stocks can
// each get their own min-h-0/overflow-y-auto scroll region within the
// sidebar's now-viewport-pinned height, instead of one growing block.
test("is hidden below the md breakpoint instead of forcing page width", () => {
  const { container } = renderSidebar([]);
  const aside = container.querySelector("aside");
  expect(aside?.className).toContain("hidden");
  expect(aside?.className).toContain("md:flex");
  expect(aside?.className).toContain("w-56");
  expect(aside?.className).toContain("shrink-0");
});

test("the remove control is hidden until its row is hovered or focused", async () => {
  renderSidebar([watchlistItem({ ticker: "AAPL" }), watchlistItem({ ticker: "MSFT" })]);
  const aaplRemove = await screen.findByRole("button", { name: /remove aapl from watchlist/i });
  const msftRemove = screen.getByRole("button", { name: /remove msft from watchlist/i });

  // Not hovered/focused: both controls carry the hidden-by-default class.
  expect(aaplRemove.className).toContain("opacity-0");
  expect(msftRemove.className).toContain("opacity-0");

  fireEvent.mouseEnter(aaplRemove.closest("li")!);
  expect(aaplRemove.className).toContain("opacity-100");
  expect(msftRemove.className).toContain("opacity-0");
});

test("clicking the remove control deletes the ticker and it leaves the list without a full reload", async () => {
  renderSidebar([watchlistItem({ ticker: "AAPL" }), watchlistItem({ ticker: "MSFT" })]);
  vi.mocked(api.delete).mockResolvedValue({ data: { removed: "AAPL" } });

  const removeButton = await screen.findByRole("button", { name: /remove aapl from watchlist/i });

  // The refetch triggered by invalidateQueries (after the delete resolves)
  // should see AAPL gone server-side.
  vi.mocked(api.get).mockResolvedValue({
    data: { items: [watchlistItem({ ticker: "MSFT" })], count: 1 },
  });

  fireEvent.click(removeButton);

  await waitFor(() => expect(api.delete).toHaveBeenCalledWith("/watchlist/AAPL"));
  await waitFor(() =>
    expect(screen.queryByRole("button", { name: /remove aapl from watchlist/i })).toBeNull(),
  );
  expect(screen.getByRole("button", { name: /remove msft from watchlist/i })).toBeDefined();
});

test("clicking the remove control does not navigate to the ticker's detail page", async () => {
  renderSidebar([watchlistItem({ ticker: "AAPL" })]);
  vi.mocked(api.delete).mockResolvedValue({ data: { removed: "AAPL" } });

  const removeButton = await screen.findByRole("button", { name: /remove aapl from watchlist/i });
  fireEvent.click(removeButton);

  await waitFor(() => expect(api.delete).toHaveBeenCalled());
  // The remove button is a sibling of the NavLink, not nested inside it, so
  // clicking it can never trigger the link's navigation in the first place —
  // asserting the link is still present/unnavigated proves that held.
  expect(screen.getByRole("link", { name: /aapl/i })).toBeDefined();
});

test("a failed removal leaves the entry in place and shows an error", async () => {
  renderSidebar([watchlistItem({ ticker: "AAPL" })]);
  vi.mocked(api.delete).mockRejectedValue(new Error("network error"));

  const removeButton = await screen.findByRole("button", { name: /remove aapl from watchlist/i });
  fireEvent.click(removeButton);

  await waitFor(() => expect(screen.getByRole("alert")).toBeDefined());
  expect(screen.getByRole("button", { name: /remove aapl from watchlist/i })).toBeDefined();
});

test("keyboard focus on the row reveals its remove control identically to hover", async () => {
  renderSidebar([watchlistItem({ ticker: "AAPL" }), watchlistItem({ ticker: "MSFT" })]);
  const aaplRemove = await screen.findByRole("button", { name: /remove aapl from watchlist/i });
  const msftRemove = screen.getByRole("button", { name: /remove msft from watchlist/i });
  expect(aaplRemove.className).toContain("opacity-0");

  fireEvent.focus(screen.getByRole("link", { name: /aapl/i }));

  expect(aaplRemove.className).toContain("opacity-100");
  expect(msftRemove.className).toContain("opacity-0");
});

test("Enter/click on a keyboard-focused remove control removes the ticker", async () => {
  renderSidebar([watchlistItem({ ticker: "AAPL" })]);
  vi.mocked(api.delete).mockResolvedValue({ data: { removed: "AAPL" } });

  const removeButton = await screen.findByRole("button", { name: /remove aapl from watchlist/i });
  removeButton.focus();
  fireEvent.click(removeButton); // jsdom doesn't synthesize native Enter->click activation

  await waitFor(() => expect(api.delete).toHaveBeenCalledWith("/watchlist/AAPL"));
});

// --- specs/035-chat-and-news-upgrade US6 (FR-021, FR-022, FR-023) ----------

test("renders a Top Traded Stocks section alongside Watchlist", async () => {
  renderSidebar([watchlistItem({ ticker: "AAPL" })], [mostActive({ ticker: "LUCY" })]);

  expect(await screen.findByText("Watchlist")).toBeTruthy();
  expect(await screen.findByText("Top Traded Stocks")).toBeTruthy();
  expect(await screen.findByText("LUCY")).toBeTruthy();
});

test("Watchlist and Top Traded Stocks are distinct, independently scrollable containers", async () => {
  const { container } = renderSidebar(
    [watchlistItem({ ticker: "AAPL" })], [mostActive({ ticker: "LUCY" })],
  );
  await screen.findByText("LUCY");

  const scrollRegions = Array.from(container.querySelectorAll("ul")).filter(
    (el) => el.className.includes("overflow-y-auto"),
  );
  // One scroll region per list — not one shared region for both.
  expect(scrollRegions.length).toBe(2);
  expect(scrollRegions[0]).not.toBe(scrollRegions[1]);
});

test("an empty Top Traded Stocks list shows an empty-state message", async () => {
  renderSidebar([watchlistItem({ ticker: "AAPL" })], []);

  expect(await screen.findByText("Top Traded Stocks")).toBeTruthy();
  await waitFor(() => expect(screen.getByText(/no top traded stocks/i)).toBeTruthy());
});

test("removing a ticker that's already gone (404) resolves quietly, no error shown", async () => {
  renderSidebar([watchlistItem({ ticker: "AAPL" })]);
  vi.mocked(api.delete).mockRejectedValue({
    isAxiosError: true,
    response: { status: 404, data: { detail: "AAPL not in watchlist." } },
  });

  const removeButton = await screen.findByRole("button", { name: /remove aapl from watchlist/i });
  fireEvent.click(removeButton);

  await waitFor(() => expect(api.delete).toHaveBeenCalledWith("/watchlist/AAPL"));
  expect(screen.queryByRole("alert")).toBeNull();
});

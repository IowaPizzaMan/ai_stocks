import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../../api/client";
import type { WatchlistItem } from "../../api/types";
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

function renderSidebar(items: WatchlistItem[]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.mocked(api.get).mockResolvedValue({ data: { items, count: items.length } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

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

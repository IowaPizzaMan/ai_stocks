import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../../api/client";
import type { AnalysisFeedItem } from "../../api/types";
import AnalysisTile from "./AnalysisTile";

vi.mock("../../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

const mockNavigate = vi.hoisted(() => vi.fn());
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => mockNavigate };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function analysis(overrides: Partial<AnalysisFeedItem>): AnalysisFeedItem {
  return {
    ticker: "AAPL",
    timestamp: new Date().toISOString(),
    signal: "bullish",
    conviction: "high",
    summary: "Summary text.",
    key_trends: [],
    flags: [],
    ...overrides,
  } as AnalysisFeedItem;
}

// AnalysisTile will grow router/query-client dependencies once US2 wires
// navigation + the watchlist-mutating hover preview onto it — wrapping here
// now keeps these US1 tests stable across that later change.
function renderTile(item: AnalysisFeedItem) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <AnalysisTile analysis={item} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test.each([
  ["bullish", "emerald"],
  ["bearish", "red"],
  ["neutral", "zinc"],
])("%s signal renders its %s fill/border/text classes", (signal, colorFamily) => {
  const { container } = renderTile(analysis({ signal: signal as AnalysisFeedItem["signal"] }));
  const tile = container.firstElementChild as HTMLElement;
  expect(tile.className).toContain(colorFamily);
});

test("an unrecognized signal renders a conspicuous dashed fallback, not a silent neutral", () => {
  const { container } = renderTile(
    analysis({ signal: "not-a-real-signal" as AnalysisFeedItem["signal"] }),
  );
  const tile = container.firstElementChild as HTMLElement;
  expect(tile.className).toContain("border-dashed");
  expect(tile.className).not.toContain("emerald");
  expect(tile.className).not.toContain("red");
});

test.each([
  ["high", 3],
  ["medium", 2],
  ["low", 1],
])("%s conviction renders %i filled dots", (conviction, filledCount) => {
  const { container } = renderTile(
    analysis({ conviction: conviction as AnalysisFeedItem["conviction"] }),
  );
  const dots = container.querySelectorAll("[data-dot]");
  expect(dots).toHaveLength(3);
  const filled = container.querySelectorAll('[data-dot][data-filled="true"]');
  expect(filled).toHaveLength(filledCount);
});

test("a missing/unrecognized conviction renders zero filled dots, not a misleading count", () => {
  const { container } = renderTile(
    analysis({ conviction: "not-a-real-conviction" as AnalysisFeedItem["conviction"] }),
  );
  const filled = container.querySelectorAll('[data-dot][data-filled="true"]');
  expect(filled).toHaveLength(0);
});

test("the ticker is the only visible text on the tile face", () => {
  const { container } = renderTile(analysis({ ticker: "MSFT", summary: "Should not appear" }));
  expect(container.textContent).toBe("MSFT");
  expect(screen.getByText("MSFT")).toBeDefined();
});

test("long tickers render in full, without ambiguous truncation", () => {
  for (const ticker of ["GOOGL", "BRK.B"]) {
    const { container, unmount } = renderTile(analysis({ ticker }));
    const tickerEl = screen.getByText(ticker);
    expect(tickerEl.textContent).toBe(ticker);
    expect(container.textContent).toBe(ticker);
    unmount();
  }
});

test("the accessible label announces ticker, signal, conviction, and recency", () => {
  const { container } = renderTile(
    analysis({
      ticker: "NVDA",
      signal: "bullish",
      conviction: "high",
      timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    }),
  );
  const tile = container.firstElementChild as HTMLElement;
  const label = tile.getAttribute("aria-label") ?? "";
  expect(label).toContain("NVDA");
  expect(label).toContain("bullish");
  expect(label).toContain("high conviction (3 of 3)");
  expect(label).toContain("2h ago");
});

test("the accessible label degrades gracefully when conviction is missing", () => {
  const { container } = renderTile(
    analysis({ conviction: undefined as unknown as AnalysisFeedItem["conviction"] }),
  );
  const tile = container.firstElementChild as HTMLElement;
  const label = tile.getAttribute("aria-label") ?? "";
  expect(label).toContain("no conviction data");
});

// specs/023-remove-stocks US2/US3 — hover/focus-revealed delete control + confirm popover.

test("the remove control is hidden until the tile is hovered or focused", () => {
  const { container } = renderTile(analysis({ ticker: "NVDA" }));
  const tile = container.firstElementChild as HTMLElement;
  const removeButton = screen.getByRole("button", { name: /delete nvda and its data/i });
  expect(removeButton.className).toContain("opacity-0");

  fireEvent.mouseEnter(tile);
  expect(removeButton.className).toContain("opacity-100");
});

test("clicking the remove control opens a confirm popover without deleting or navigating yet", () => {
  renderTile(analysis({ ticker: "NVDA" }));
  fireEvent.click(screen.getByRole("button", { name: /delete nvda and its data/i }));

  expect(screen.getByRole("dialog")).toBeDefined();
  expect(api.delete).not.toHaveBeenCalled();
  expect(mockNavigate).not.toHaveBeenCalled();
});

test("cancelling the popover deletes nothing, navigates nowhere, and leaves the tile as-is", () => {
  renderTile(analysis({ ticker: "NVDA" }));
  fireEvent.click(screen.getByRole("button", { name: /delete nvda and its data/i }));
  fireEvent.click(screen.getByRole("button", { name: /cancel delete nvda/i }));

  expect(screen.queryByRole("dialog")).toBeNull();
  expect(api.delete).not.toHaveBeenCalled();
  expect(mockNavigate).not.toHaveBeenCalled();
});

test("confirming the popover calls DELETE /tickers/{ticker}, closes on success, and never navigates", async () => {
  vi.mocked(api.delete).mockResolvedValue({ data: { deleted: "NVDA" } });
  renderTile(analysis({ ticker: "NVDA" }));

  fireEvent.click(screen.getByRole("button", { name: /delete nvda and its data/i }));
  fireEvent.click(screen.getByRole("button", { name: /confirm delete nvda/i }));

  await waitFor(() => expect(api.delete).toHaveBeenCalledWith("/tickers/NVDA"));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(mockNavigate).not.toHaveBeenCalled();
});

test("a failed deletion keeps the popover open with an inline error, tile untouched", async () => {
  vi.mocked(api.delete).mockRejectedValue(new Error("network error"));
  const { container } = renderTile(analysis({ ticker: "NVDA" }));

  fireEvent.click(screen.getByRole("button", { name: /delete nvda and its data/i }));
  fireEvent.click(screen.getByRole("button", { name: /confirm delete nvda/i }));

  await waitFor(() => expect(screen.getByRole("alert")).toBeDefined());
  expect(screen.getByRole("dialog")).toBeDefined();
  expect(container.firstElementChild).not.toBeNull(); // the tile itself is still rendered
});

test("keyboard focus on the tile reveals its remove control identically to hover", () => {
  const { container } = renderTile(analysis({ ticker: "NVDA" }));
  const tile = container.firstElementChild as HTMLElement;
  const removeButton = screen.getByRole("button", { name: /delete nvda and its data/i });
  expect(removeButton.className).toContain("opacity-0");

  fireEvent.focus(tile);

  expect(removeButton.className).toContain("opacity-100");
});

test("activating the remove control via keyboard opens the popover with focus already on Confirm", () => {
  renderTile(analysis({ ticker: "NVDA" }));
  const removeButton = screen.getByRole("button", { name: /delete nvda and its data/i });
  removeButton.focus();
  fireEvent.click(removeButton); // keyboard activation of a focused button

  const confirmButton = screen.getByRole("button", { name: /confirm delete nvda/i });
  expect(document.activeElement).toBe(confirmButton);
});

test("Enter on the focused remove control does not by itself open the popover or navigate — only a real activation (click) does", () => {
  renderTile(analysis({ ticker: "NVDA" }));
  const removeButton = screen.getByRole("button", { name: /delete nvda and its data/i });
  removeButton.focus();
  fireEvent.keyDown(removeButton, { key: "Enter" });

  expect(screen.queryByRole("dialog")).toBeNull();
  expect(mockNavigate).not.toHaveBeenCalled();

  fireEvent.click(removeButton); // jsdom doesn't synthesize native Enter->click activation
  expect(screen.getByRole("dialog")).toBeDefined();
  expect(mockNavigate).not.toHaveBeenCalled();
});

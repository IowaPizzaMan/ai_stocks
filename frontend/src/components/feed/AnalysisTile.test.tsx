import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test } from "vitest";
import type { AnalysisFeedItem } from "../../api/types";
import AnalysisTile from "./AnalysisTile";

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

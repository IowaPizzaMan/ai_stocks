import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../../api/client";
import type { AnalysisFeedItem } from "../../api/types";
import TilePreview from "./TilePreview";

vi.mock("../../api/client", () => ({ api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function analysis(overrides: Partial<AnalysisFeedItem>): AnalysisFeedItem {
  return {
    ticker: "AAPL",
    timestamp: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
    signal: "bullish",
    conviction: "high",
    summary: "Apple presents a high-conviction long setup.",
    key_trends: [],
    flags: [],
    ...overrides,
  } as AnalysisFeedItem;
}

function renderPreview(item: AnalysisFeedItem, onWrapperClick = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.mocked(api.post).mockResolvedValue({ data: { ticker: item.ticker } });
  const utils = render(
    <QueryClientProvider client={queryClient}>
      {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
      <div onClick={onWrapperClick}>
        <TilePreview analysis={item} />
      </div>
    </QueryClientProvider>,
  );
  return { ...utils, onWrapperClick };
}

test("shows the signal as readable text", () => {
  renderPreview(analysis({ signal: "bullish" }));
  expect(screen.getByText("bullish")).toBeDefined();
});

test("shows conviction with its label, not just dots", () => {
  renderPreview(analysis({ conviction: "high" }));
  expect(screen.getByText(/high conviction/i)).toBeDefined();
});

test("shows relative recency", () => {
  renderPreview(analysis({}));
  expect(screen.getByText("3h ago")).toBeDefined();
});

test("shows the analysis summary", () => {
  renderPreview(analysis({ summary: "A distinctive summary sentence." }));
  expect(screen.getByText("A distinctive summary sentence.")).toBeDefined();
});

test("clicking the watchlist button adds the ticker without navigating (stopPropagation to the tile)", async () => {
  const onWrapperClick = vi.fn();
  const { getByRole } = renderPreview(analysis({ ticker: "NVDA" }), onWrapperClick);

  fireEvent.click(getByRole("button", { name: /watchlist/i }));

  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/watchlist/NVDA"));
  expect(onWrapperClick).not.toHaveBeenCalled();
});

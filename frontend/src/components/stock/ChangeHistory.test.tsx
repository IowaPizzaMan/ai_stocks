import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../../api/client";
import type { StockEvent, TickerChangeHistoryResponse } from "../../api/types";
import ChangeHistory from "./ChangeHistory";

vi.mock("../../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function mockHistory(items: StockEvent[]) {
  vi.mocked(api.get).mockImplementation(async (url: string) => {
    if (url === "/events/AVB") {
      const body: TickerChangeHistoryResponse = { ticker: "AVB", items, total: items.length, limit: 20 };
      return { data: body };
    }
    throw new Error(`unexpected GET ${url}`);
  });
}

function renderHistory() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ChangeHistory ticker="AVB" />
    </QueryClientProvider>,
  );
}

test("a conviction-only change renders the transition and its rule-derived reason", async () => {
  mockHistory([
    { ticker: "AVB", event_type: "added", occurred_at: "2026-09-01T00:00:00Z",
      changed: false, changes: null, reason: null },
    { ticker: "AVB", event_type: "updated", occurred_at: "2026-09-04T00:00:00Z", changed: true,
      changes: { conviction: { from: "medium", to: "high", changed: true } },
      reason: "strategy alignment changed — all three entry strategies aligned" },
  ]);
  renderHistory();

  await waitFor(() => expect(screen.getByText(/conviction medium→high/)).toBeDefined());
  expect(screen.getByText(/strategy alignment changed/)).toBeDefined();
});

test("a signal+conviction change renders both transitions together", async () => {
  mockHistory([
    { ticker: "AVB", event_type: "added", occurred_at: "2026-09-01T00:00:00Z",
      changed: false, changes: null, reason: null },
    { ticker: "AVB", event_type: "updated", occurred_at: "2026-09-04T00:00:00Z", changed: true,
      changes: {
        signal: { from: "neutral", to: "bullish", changed: true },
        conviction: { from: "medium", to: "high", changed: true },
      },
      reason: "revenue trend changed — all conditions now pass" },
  ]);
  renderHistory();

  await waitFor(() => expect(screen.getByText(/signal neutral→bullish/)).toBeDefined());
  expect(screen.getByText(/conviction medium→high/)).toBeDefined();
});

test("a reason-less entry renders the transition without an em-dash reason clause", async () => {
  mockHistory([
    { ticker: "AVB", event_type: "added", occurred_at: "2026-09-01T00:00:00Z",
      changed: false, changes: null, reason: null },
    { ticker: "AVB", event_type: "updated", occurred_at: "2026-09-04T00:00:00Z", changed: true,
      changes: { signal: { from: "neutral", to: "bearish", changed: true } }, reason: null },
  ]);
  renderHistory();

  await waitFor(() => expect(screen.getByText(/signal neutral→bearish/)).toBeDefined());
  expect(screen.queryByText(/—/)).toBeNull();
});

test("a ticker with only its added event shows the near-empty state, not a blank list", async () => {
  mockHistory([
    { ticker: "AVB", event_type: "added", occurred_at: "2026-09-01T00:00:00Z",
      changed: false, changes: null, reason: null },
  ]);
  renderHistory();

  await waitFor(() => expect(screen.getByText(/no changes recorded yet/i)).toBeDefined());
  expect(screen.queryByRole("list")).toBeNull();
});

test("a ticker with no events at all shows a plain no-history message", async () => {
  mockHistory([]);
  renderHistory();

  await waitFor(() => expect(screen.getByText("No history yet.")).toBeDefined());
});

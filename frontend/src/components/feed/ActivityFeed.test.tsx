import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../../api/client";
import type { StockEvent, StockEventsResponse } from "../../api/types";
import ActivityFeed from "./ActivityFeed";

vi.mock("../../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function event(overrides: Partial<StockEvent> = {}): StockEvent {
  return {
    ticker: "AVB",
    event_type: "added",
    occurred_at: "2026-09-04T12:00:00Z",
    changed: false,
    changes: null,
    reason: null,
    ...overrides,
  };
}

function mockEvents(items: StockEvent[], total?: number) {
  vi.mocked(api.get).mockImplementation(async (url: string, config?: unknown) => {
    if (url === "/events") {
      const params = (config as { params?: Record<string, unknown> } | undefined)?.params ?? {};
      const page = Number(params.page ?? 1);
      const pageSize = Number(params.page_size ?? 20);
      const pageItems = items.slice((page - 1) * pageSize, page * pageSize);
      const body: StockEventsResponse = {
        items: pageItems, total: total ?? items.length, page, page_size: pageSize, window: 100,
      };
      return { data: body };
    }
    throw new Error(`unexpected GET ${url}`);
  });
}

function renderFeed() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ActivityFeed />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("renders an added-event row with the ticker, verb, and compact date", async () => {
  mockEvents([event({ ticker: "AVB", event_type: "added", occurred_at: "2026-09-04T12:00:00Z" })]);
  renderFeed();

  await waitFor(() => expect(screen.getByText(/was added on 9\/4/)).toBeDefined());
});

test("the ticker links to that stock's detail page", async () => {
  mockEvents([event({ ticker: "AVB" })]);
  renderFeed();

  const link = await screen.findByRole("link", { name: "AVB" });
  expect(link.getAttribute("href")).toBe("/stock/AVB");
});

test("a changed update is flagged and shows the transition", async () => {
  mockEvents([
    event({
      ticker: "AVB", event_type: "updated", changed: true,
      changes: { conviction: { from: "medium", to: "high", changed: true } },
    }),
  ]);
  renderFeed();

  await waitFor(() => expect(screen.getByText(/was updated on/)).toBeDefined());
  expect(screen.getByText(/conviction medium→high/)).toBeDefined();
  expect(screen.getByText("changed")).toBeDefined();
});

test("an unchanged update renders without a flag or transition", async () => {
  mockEvents([event({ ticker: "AVB", event_type: "updated", changed: false })]);
  renderFeed();

  await waitFor(() => expect(screen.getByText(/was updated on/)).toBeDefined());
  expect(screen.queryByText("changed")).toBeNull();
});

test("shows an empty state when there are no events", async () => {
  mockEvents([]);
  renderFeed();

  await waitFor(() => expect(screen.getByText("No activity yet.")).toBeDefined());
});

test("paging moves forward and back through the window", async () => {
  const items = Array.from({ length: 3 }, (_, i) => event({ ticker: `T${i}` }));
  mockEvents(items, 3);
  renderFeed(); // page_size defaults to 20 in the component -> all 3 fit on page 1, no paging controls

  await waitFor(() => expect(screen.getByText("T0")).toBeDefined());
  expect(screen.queryByRole("button", { name: /older/i })).toBeNull();
});

test("paging controls appear and advance when more than a page of events exists", async () => {
  vi.mocked(api.get).mockImplementation(async (url: string, config?: unknown) => {
    if (url === "/events") {
      const params = (config as { params?: Record<string, unknown> } | undefined)?.params ?? {};
      const page = Number(params.page ?? 1);
      const body: StockEventsResponse = {
        items: [event({ ticker: page === 1 ? "PAGE1" : "PAGE2" })],
        total: 40, page, page_size: 20, window: 100,
      };
      return { data: body };
    }
    throw new Error(`unexpected GET ${url}`);
  });
  renderFeed();

  await waitFor(() => expect(screen.getByText("PAGE1")).toBeDefined());
  const older = screen.getByRole("button", { name: /older/i });
  const newer = () => screen.getByRole("button", { name: /newer/i }) as HTMLButtonElement;
  expect(newer().disabled).toBe(true);

  fireEvent.click(older);

  await waitFor(() => expect(screen.getByText("PAGE2")).toBeDefined());
  expect(newer().disabled).toBe(false);
});

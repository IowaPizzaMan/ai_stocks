// specs/028-dashboard-tweaks-batch US6 (FR-022, FR-023, FR-024)
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../../api/client";
import type { MostActivesResponse, QueueStatus } from "../../api/types";
import MostActivesPanel from "./MostActivesPanel";

vi.mock("../../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function response(overrides: Partial<MostActivesResponse> = {}): MostActivesResponse {
  return {
    items: [
      { ticker: "LUCY", company: "Innovative Eyewear, Inc.", price: 1.85, change: 0.06, change_pct: 3.35196, exchange: "NASDAQ" },
      { ticker: "ZWQ", company: "Zwq Corp", price: 42.0, change: -1.1, change_pct: -2.55, exchange: "NYSE" },
    ],
    as_of: "2026-08-22T09:00:00Z",
    date: "2026-08-22",
    ...overrides,
  };
}

function renderPanel({
  body = response(),
  fail = false,
  queue = { pending: [], running: [], pending_count: 0, running_count: 0 } as QueueStatus,
}: { body?: MostActivesResponse; fail?: boolean; queue?: QueueStatus } = {}) {
  vi.mocked(api.get).mockImplementation(async (url: string) => {
    if (url === "/market/most-actives") {
      if (fail) throw new Error("boom");
      return { data: body };
    }
    if (url === "/queue") return { data: queue };
    throw new Error(`unexpected GET ${url}`);
  });
  vi.mocked(api.post).mockResolvedValue({ data: { status: "enqueued", job_id: "job-1" } });

  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <MostActivesPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("renders rows in the order the API returns them (rank order)", async () => {
  const { container } = renderPanel();
  await waitFor(() => expect(screen.getByText("LUCY")).toBeTruthy());
  const tickerCells = container.querySelectorAll("[data-ticker]");
  expect(Array.from(tickerCells).map((el) => el.getAttribute("data-ticker"))).toEqual(["LUCY", "ZWQ"]);
});

test("each ticker links to the singular /stock/<TICKER> route", async () => {
  const { container } = renderPanel();
  await waitFor(() => expect(screen.getByText("LUCY")).toBeTruthy());
  expect(container.querySelector('a[href="/stock/LUCY"]')).toBeTruthy();
});

test("shows the served session date", async () => {
  renderPanel();
  await waitFor(() => expect(screen.getByText(/session/i)).toBeTruthy());
  expect(screen.getByText(/session/i).textContent).toMatch(/2026/);
});

test("no volume column is rendered anywhere", async () => {
  renderPanel();
  await waitFor(() => expect(screen.getByText("LUCY")).toBeTruthy());
  expect(screen.queryByText(/volume/i)).toBeNull();
});

test("a change_pct of 3.35196 renders as +3.35%, not +335.20%", async () => {
  renderPanel();
  await waitFor(() => expect(screen.getByText("+3.35%")).toBeTruthy());
  expect(screen.queryByText(/335\.2/)).toBeNull();
});

test("a negative change_pct renders with a minus sign, not just color", async () => {
  renderPanel();
  await waitFor(() => expect(screen.getByText("-2.55%")).toBeTruthy());
});

test("shows an empty state before any refresh has happened", async () => {
  renderPanel({ body: { items: [], as_of: null, date: null } });
  await waitFor(() => expect(screen.getByText(/no data yet/i)).toBeTruthy());
});

test("shows an unavailable message on request failure, not a blank section", async () => {
  renderPanel({ fail: true });
  await waitFor(() => expect(screen.getByText(/unavailable/i)).toBeTruthy());
});

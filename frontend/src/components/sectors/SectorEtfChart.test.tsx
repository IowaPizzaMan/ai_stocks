// specs/028-dashboard-tweaks-batch US5 (FR-019, FR-020a, FR-020b, FR-021)
// specs/029-company-profile-tweaks US4 (FR-028-FR-032) — taller chart, a
// custom ClickableLegend.
//
// Recharts' own <Line>/<Legend> children don't render into jsdom's zero-size
// ResponsiveContainer (same limitation YieldCurveChart.test.tsx documents) —
// so the 11-lines/per-color requirement is covered by code review (one
// <Line> per data.series entry, TICKER_COLORS keyed by ticker) rather than
// asserted here. ClickableLegend is different: it's a plain <ul>/<button>
// list rendered as a sibling of ResponsiveContainer, not a Recharts child
// needing SVG measurement, so its interactions (click, aria-pressed, keyboard
// focus) render and respond normally in jsdom and are asserted directly.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useSearchParams } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../../api/client";
import type { QueueStatus, SectorEtfSeriesResponse } from "../../api/types";
import SectorEtfChart from "./SectorEtfChart";

vi.mock("../../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const ALL_TICKERS = ["XLC", "XLY", "XLP", "XLE", "XLF", "XLI", "XLV", "XLB", "XLRE", "XLK", "XLU"];

function seriesResponse(overrides: Partial<SectorEtfSeriesResponse> = {}): SectorEtfSeriesResponse {
  return {
    window: "6m",
    series: ALL_TICKERS.map((ticker, i) => ({
      ticker,
      label: `${ticker} sector`,
      bars: [
        { date: "2026-01-01", close: 100 + i },
        { date: "2026-01-02", close: 101 + i },
      ],
      partial: false,
    })),
    as_of: "2026-08-22T09:00:00Z",
    ...overrides,
  };
}

function ParamsProbe() {
  const [params] = useSearchParams();
  return <span data-testid="params">{params.toString()}</span>;
}

function renderChart({
  body = seriesResponse(),
  fail = false,
  initial = "/sectors",
}: { body?: SectorEtfSeriesResponse; fail?: boolean; initial?: string } = {}) {
  vi.mocked(api.get).mockImplementation(async (url: string) => {
    if (url === "/sectors/etf-series") {
      if (fail) throw new Error("boom");
      return { data: body };
    }
    if (url === "/queue") {
      return { data: { pending: [], running: [], pending_count: 0, running_count: 0 } as QueueStatus };
    }
    throw new Error(`unexpected GET ${url}`);
  });
  vi.mocked(api.post).mockResolvedValue({ data: { status: "enqueued", job_id: "job-1" } });

  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initial]}>
        <Routes>
          <Route
            path="/sectors"
            element={
              <>
                <SectorEtfChart />
                <ParamsProbe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function waitForLoaded() {
  await waitFor(() => expect(screen.queryByText(/loading sector chart/i)).toBeNull());
}

test("shows an empty state before any refresh has happened", async () => {
  renderChart({ body: { window: "6m", series: [], as_of: "" } });
  await waitFor(() => expect(screen.getByText(/no data yet/i)).toBeTruthy());
});

test("renders a full 11-series response without crashing", async () => {
  renderChart();
  await waitForLoaded();
  expect(screen.getByText("Sector Momentum")).toBeTruthy();
  expect(screen.queryByText(/unavailable/i)).toBeNull();
  expect(screen.queryByText(/no data yet/i)).toBeNull();
});

test("a zero-bar series does not prevent the others rendering and is named in the note", async () => {
  const body = seriesResponse();
  body.series = body.series.map((s) => (s.ticker === "XLRE" ? { ...s, bars: [], partial: true } : s));
  renderChart({ body });

  await waitForLoaded();
  // still renders the chart, not the empty state, since 10 of 11 have data
  expect(screen.queryByText(/no data yet/i)).toBeNull();
  expect(screen.getByText(/Limited history/i).textContent).toContain("XLRE");
});

test("no partial note appears when every series has data", async () => {
  renderChart();
  await waitForLoaded();
  expect(screen.queryByText(/Limited history/i)).toBeNull();
});

test("window selection round-trips through the URL and refetches", async () => {
  renderChart();
  await waitForLoaded();
  vi.mocked(api.get).mockClear();

  fireEvent.click(screen.getByRole("button", { name: "1Y" }));

  await waitFor(() => expect(screen.getByTestId("params").textContent).toBe("window=1y"));
  await waitFor(() =>
    expect(api.get).toHaveBeenCalledWith("/sectors/etf-series", { params: { window: "1y" } }),
  );
});

test("defaults to 6m when no window param is present", async () => {
  renderChart();
  await waitForLoaded();
  expect(api.get).toHaveBeenCalledWith("/sectors/etf-series", { params: { window: "6m" } });
});

test("reads the window from the URL on load", async () => {
  renderChart({ initial: "/sectors?window=1y" });
  await waitFor(() =>
    expect(api.get).toHaveBeenCalledWith("/sectors/etf-series", { params: { window: "1y" } }),
  );
});

test("shows an unavailable-style message on request failure", async () => {
  renderChart({ fail: true });
  await waitFor(() => expect(screen.getByText(/unavailable/i)).toBeTruthy());
});

// --- specs/029-company-profile-tweaks US4 (FR-028-FR-032) -------------------

test("renders at the taller 440px height", async () => {
  const { container } = renderChart();
  await waitForLoaded();

  const wrapper = container.querySelector(".recharts-responsive-container") as HTMLElement | null;
  expect(wrapper).not.toBeNull();
  expect(wrapper?.style.height).toBe("440px");
});

test("clicking a legend ticker hides it, marks it aria-pressed, and clicking again restores it", async () => {
  renderChart();
  await waitForLoaded();

  const legendButton = screen.getByRole("button", { name: "XLK" });
  expect(legendButton.getAttribute("aria-pressed")).toBe("false");

  fireEvent.click(legendButton);
  expect(legendButton.getAttribute("aria-pressed")).toBe("true");
  expect(legendButton.className).toContain("line-through");

  fireEvent.click(legendButton);
  expect(legendButton.getAttribute("aria-pressed")).toBe("false");
  expect(legendButton.className).not.toContain("line-through");
});

test("hidden series survive a window change", async () => {
  renderChart();
  await waitForLoaded();

  fireEvent.click(screen.getByRole("button", { name: "XLK" }));
  expect(screen.getByRole("button", { name: "XLK" }).getAttribute("aria-pressed")).toBe("true");

  fireEvent.click(screen.getByRole("button", { name: "1Y" }));
  await waitFor(() => expect(screen.getByTestId("params").textContent).toBe("window=1y"));
  await waitForLoaded();

  expect(screen.getByRole("button", { name: "XLK" }).getAttribute("aria-pressed")).toBe("true");
});

test("hiding every series shows a distinct 'all hidden' message, not the 'no data' empty state", async () => {
  renderChart();
  await waitForLoaded();

  for (const ticker of ALL_TICKERS) {
    fireEvent.click(screen.getByRole("button", { name: ticker }));
  }

  expect(screen.getByText(/all series hidden/i)).toBeTruthy();
  expect(screen.queryByText(/no data yet/i)).toBeNull();
  // the legend itself is still there so the user can bring a series back
  expect(screen.getByRole("button", { name: "XLK" })).toBeTruthy();
});

test("a legend entry is a real button, keyboard-focusable and clickable via Enter semantics", async () => {
  renderChart();
  await waitForLoaded();

  const legendButton = screen.getByRole("button", { name: "XLU" });
  expect(legendButton.tagName).toBe("BUTTON");
  legendButton.focus();
  expect(document.activeElement).toBe(legendButton);
});

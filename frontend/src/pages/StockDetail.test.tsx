import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { api } from "../api/client";
import type { Analysis } from "../api/types";
import StockDetail from "./StockDetail";

vi.mock("../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, value: 800 });
  Object.defineProperty(HTMLElement.prototype, "clientHeight", { configurable: true, value: 400 });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
    width: 800, height: 400, top: 0, left: 0, bottom: 400, right: 800, x: 0, y: 0, toJSON: () => {},
  } as DOMRect);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const bars = Array.from({ length: 60 }, (_, i) => ({
  date: `2026-01-${String((i % 28) + 1).padStart(2, "0")}`,
  open: 100 + i,
  high: 102 + i,
  low: 98 + i,
  close: 100.5 + i,
  volume: 1000,
}));

function analysis(overrides: Partial<Analysis> = {}): Analysis {
  return {
    ticker: "AAPL",
    timestamp: "2026-08-15T12:00:00Z",
    signal: "bullish",
    conviction: "high",
    summary:
      "AAPL is holding above support at 182.50. Momentum has improved over the last two weeks. " +
      "Volume confirms the move. Risk remains if the gap fills.",
    key_trends: ["Momentum improving"],
    flags: ["Gap unfilled"],
    position_management: {
      stair_step_stops: [180.5, 175.25],
      trailing_stop_recommendation: "Trail below the 21 EMA.",
      position_sizing: "Half size until confirmation.",
    },
    sub_reports: {
      technical: {
        overall_technical_signal: "bullish",
        confidence: "high",
        momentum_summary: "Momentum is improving.",
        tfc_narrative: "Timeframes agree.",
        bf_position_narrative: "Mid-range.",
        volume_narrative: "Volume confirms.",
      },
      recommendation: {
        recommendation: "HOLD",
        conviction: "medium",
        rationale: "Market internals are neutral here.",
        nymo_current: -15,
        namo_current: -10,
        nymo_signal: "neutral",
        caveats: ["This ticker has an upward gap from 2026-07-27 that was filled within two days."],
      },
    },
    ...overrides,
  };
}

function renderPage(hash = "", data: Analysis | null = analysis()) {
  (api.get as ReturnType<typeof vi.fn>).mockImplementation((url: string) => {
    if (url.includes("/price")) return Promise.resolve({ data: { bars } });
    if (url.includes("/queue")) return Promise.resolve({ data: { pending: [], running: [] } });
    if (url.match(/\/stocks\/[^/]+$/)) return Promise.resolve({ data: { ticker: "AAPL", name: "Apple" } });
    if (url.includes("/analysis")) {
      return data
        ? Promise.resolve({ data })
        : Promise.reject(Object.assign(new Error("not found"), { response: { status: 404 } }));
    }
    return Promise.resolve({ data: {} });
  });

  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/stocks/AAPL${hash}`]}>
        <Routes>
          <Route path="/stocks/:ticker" element={<StockDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// --- US1: Charts tab is the default ----------------------------------------

test("defaults to the Charts tab when no hash is given", async () => {
  renderPage();
  await waitFor(() => expect(screen.getByText(/rate of change/i)).toBeTruthy());
  expect(screen.getAllByText("Daily").length).toBeGreaterThan(0);
});

test("an explicit #overview hash still opens the Overview tab", async () => {
  renderPage("#overview");
  await waitFor(() => expect(screen.getByText("Verdict")).toBeTruthy());
});

test("an unknown hash falls back to the Charts tab", async () => {
  renderPage("#bogus-removed-tab");
  await waitFor(() => expect(screen.getByText(/rate of change/i)).toBeTruthy());
});

test("no Deep Dive section exists anywhere on the page", async () => {
  renderPage();
  await waitFor(() => expect(screen.getByText(/rate of change/i)).toBeTruthy());
  expect(screen.queryByText(/deep dive/i)).toBeNull();
});

test("charts render even when the ticker has no analysis yet", async () => {
  renderPage("", null);
  // wait for the analysis query to settle, not just for the charts to mount
  await waitFor(() => expect(screen.getByText(/charts below still render/i)).toBeTruthy());
  expect(screen.getByText(/rate of change/i)).toBeTruthy();
  expect(screen.getAllByText("Daily").length).toBeGreaterThan(0);
});

// --- US4: readable prose, no Position Management ----------------------------

test("the Overview verdict renders as structured prose, not one block", async () => {
  renderPage("#overview");
  await waitFor(() => expect(screen.getByText("Verdict")).toBeTruthy());
  // 4 sentences → bullets
  const section = screen.getByText("Verdict").closest("section")!;
  expect(section.querySelectorAll("li").length).toBeGreaterThan(1);
});

test("key terms in the verdict are emphasized", async () => {
  renderPage("#overview");
  await waitFor(() => expect(screen.getByText("Verdict")).toBeTruthy());
  const section = screen.getByText("Verdict").closest("section")!;
  const strongs = [...section.querySelectorAll("strong")].map((s) => s.textContent);
  expect(strongs).toContain("182.50");
  expect(strongs).toContain("AAPL");
});

test("the Overview tab no longer renders Position Management", async () => {
  renderPage("#overview");
  await waitFor(() => expect(screen.getByText("Verdict")).toBeTruthy());
  expect(screen.queryByText(/position management/i)).toBeNull();
  expect(screen.queryByText(/stair-step stops/i)).toBeNull();
});

// --- US8: AI Summary refresh ------------------------------------------------

test("AI Summary keeps market-timing caveats but drops the breadth chart", async () => {
  const { container } = renderPage("#ai-summary");
  await waitFor(() => expect(screen.getByText(/market timing/i)).toBeTruthy());
  expect(screen.getByText(/upward gap from 2026-07-27/)).toBeTruthy();
  // BreadthDivergenceChart is the only chart this tab used to render
  expect(container.querySelector(".recharts-wrapper")).toBeNull();
  expect(screen.queryByText(/divergence/i)).toBeNull();
});

test("AI Summary shows a news stance when one exists", async () => {
  const withNews = analysis();
  withNews.sub_reports.news = {
    articles: [],
    timeline: [],
    trend: "bullish",
    stance: { direction: "bullish", reasoning: "'Record quarter' outweighs the review." },
    news_count: 4,
    as_of: "2026-08-15",
  };
  renderPage("#ai-summary", withNews);
  await waitFor(() => expect(screen.getByText(/news stance/i)).toBeTruthy());
  expect(screen.getByText(/outweighs the review/)).toBeTruthy();
});

test("AI Summary reports what changed since the last analysis", async () => {
  const withChanges = analysis({
    changes_since_last: {
      previous_timestamp: "2026-08-01T00:00:00Z",
      signal: { from: "neutral", to: "bullish", changed: true },
      conviction: { from: "low", to: "high", changed: true },
      flags_added: ["Gap unfilled"],
      flags_removed: [],
    },
  });
  renderPage("#ai-summary", withChanges);
  await waitFor(() => expect(screen.getByText(/what changed since the last analysis/i)).toBeTruthy());
  expect(screen.getByText(/Signal moved from/)).toBeTruthy();
});

test("AI Summary omits the changes section on a first-ever analysis", async () => {
  renderPage("#ai-summary");
  await waitFor(() => expect(screen.getByText(/market timing/i)).toBeTruthy());
  expect(screen.queryByText(/what changed since the last analysis/i)).toBeNull();
});

// --- tab bar ----------------------------------------------------------------

test("the tab bar lists Charts first and includes News", async () => {
  renderPage();
  await waitFor(() => expect(screen.getByText(/rate of change/i)).toBeTruthy());
  const tabs = [...document.querySelectorAll("nav button")].map((b) => b.textContent);
  expect(tabs[0]).toBe("Charts");
  expect(tabs).toContain("News");
  expect(tabs).toContain("Overview");
});

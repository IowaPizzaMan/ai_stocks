import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../api/client";
import type {
  EconomicCalendar,
  EconomicIndicators,
  MarketBreadth,
  MarketFlowEvent,
  RiskPremium,
  TreasuryCurve,
} from "../api/types";
import Macro from "./Macro";

vi.mock("../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function flowEvent(overrides: Partial<MarketFlowEvent> = {}): MarketFlowEvent {
  return {
    event_id: "evt-1",
    category: "market_flow",
    kind: "breadth_divergence",
    divergence_type: "bullish",
    headline: "Breadth divergence detected",
    body: "NYMO diverging from price.",
    price_points: [],
    osc_points: [],
    nymo_current: 12,
    detected_on: new Date().toISOString(),
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

function breadth(overrides: Partial<MarketBreadth> = {}): MarketBreadth {
  return {
    spy: [{ date: "2026-08-01", close: 625 }],
    nymo: [{ date: "2026-08-01", value: 12 }],
    namo: [{ date: "2026-08-01", value: 9 }],
    divergence: { type: "none", description: "", price_points: [], osc_points: [] },
    divergence_history: [],
    as_of: "2026-08-01",
    method: "computed_ratio_adjusted",
    ...overrides,
  };
}

function treasuryCurve(overrides: Partial<TreasuryCurve> = {}): TreasuryCurve {
  return {
    as_of: "2026-08-19T21:00:00Z",
    stale: false,
    session: "2026-08-19",
    curve: [{ maturity: "10Y", months: 120, current: 4.65, month_ago: 4.58, year_ago: null }],
    comparison_sessions: { month_ago: "2026-07-20", year_ago: null },
    spreads: [
      { key: "10y-2y", label: "10y – 2y", current_bps: 46, change_bps: -4,
        inverted: false, series: [] },
      { key: "30y-10y", label: "30y – 10y", current_bps: null, change_bps: null,
        inverted: false, series: [] },
      { key: "10y-3m", label: "10y – 3m", current_bps: null, change_bps: null,
        inverted: false, series: [] },
    ],
    ...overrides,
  };
}

function economicCalendar(overrides: Partial<EconomicCalendar> = {}): EconomicCalendar {
  return {
    as_of: "2026-08-19T21:00:00Z",
    stale: false,
    timezone: "America/New_York",
    upcoming: [],
    reported: [],
    ...overrides,
  };
}

function economicIndicators(overrides: Partial<EconomicIndicators> = {}): EconomicIndicators {
  return {
    as_of: "2026-08-19T21:00:00Z",
    stale: false,
    indicators: [],
    ...overrides,
  };
}

function riskPremium(overrides: Partial<RiskPremium> = {}): RiskPremium {
  return {
    as_of: "2026-08-19T21:00:00Z",
    stale: false,
    country: "United States",
    total_equity_risk_premium: 4.46,
    country_risk_premium: 0.23,
    collected_at: "2026-08-19T21:00:00Z",
    ...overrides,
  };
}

function mockApi({
  flowEvents = [],
  breadth: breadthData,
  curve = treasuryCurve(),
  calendar = economicCalendar(),
  indicators = economicIndicators(),
  riskPremium: riskPremiumData = riskPremium(),
}: {
  flowEvents?: MarketFlowEvent[];
  breadth?: MarketBreadth | null;
  curve?: TreasuryCurve | null;
  calendar?: EconomicCalendar | null;
  indicators?: EconomicIndicators | null;
  riskPremium?: RiskPremium | null;
} = {}) {
  vi.mocked(api.get).mockImplementation(async (url: string) => {
    if (url === "/market/flow-events") return { data: flowEvents };
    if (url === "/market/breadth") return { data: breadthData };
    if (url === "/market/treasury-curve") return { data: curve };
    if (url === "/market/economic-calendar") return { data: calendar };
    if (url === "/market/economic-indicators") return { data: indicators };
    if (url === "/market/risk-premium") return { data: riskPremiumData };
    throw new Error(`unexpected GET ${url}`);
  });
}

function renderMacro() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/macro"]}>
        <Macro />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("renders exactly one breadth visualization, inside the market-flow card", async () => {
  mockApi({ breadth: breadth(), flowEvents: [flowEvent()] });

  const { container } = renderMacro();

  await waitFor(() => expect(screen.getByText("Breadth divergence detected")).toBeDefined());
  // One <article> shell (MarketFlowCard) — the standalone duplicate chart is gone.
  expect(container.querySelectorAll("article")).toHaveLength(1);
  expect(screen.getByText(/NYMO diverging from price/)).toBeDefined();
});

test("the breadth panel renders even with no active market-flow event", async () => {
  mockApi({ breadth: breadth(), flowEvents: [] });

  const { container } = renderMacro();

  await waitFor(() => expect(screen.getByText("Market breadth")).toBeDefined());
  expect(container.querySelectorAll("article")).toHaveLength(1);
});

test("renders zero sector-commentary cards even though the old sector UI is gone", async () => {
  mockApi({ breadth: breadth(), flowEvents: [flowEvent()] });

  renderMacro();

  await waitFor(() => expect(screen.getByText("Breadth divergence detected")).toBeDefined());
  expect(screen.queryByText("Technology")).toBeNull();
  expect(screen.queryByText(/confidence:/)).toBeNull();
  expect(screen.queryByText(/sector rotation/i)).toBeNull();
});

test("renders no breadth panel at all while breadth has not loaded", async () => {
  mockApi({ breadth: null, flowEvents: [] });

  const { container } = renderMacro();

  await waitFor(() =>
    expect(api.get).toHaveBeenCalledWith("/market/breadth", { params: { lookback_days: 60 } }),
  );
  expect(container.querySelectorAll("article")).toHaveLength(0);
});

test("renders the yield curve section below breadth, with its own freshness line", async () => {
  mockApi({ breadth: breadth(), flowEvents: [], curve: treasuryCurve() });

  renderMacro();

  await waitFor(() => expect(screen.getByText("Rates & yield curve")).toBeDefined());
  expect(screen.getByText("session 2026-08-19")).toBeDefined();
  expect(screen.getByText("10y – 2y")).toBeDefined();
});

test("renders the economic calendar section below the yield curve, with its own freshness line", async () => {
  const calendar = economicCalendar({
    upcoming: [{ date: "2026-09-04T12:30:00Z", event: "NFP", impact: "High", previous: 3.2, estimate: 3.3, unit: "%" }],
  });
  mockApi({ breadth: breadth(), flowEvents: [], calendar });

  renderMacro();

  await waitFor(() => expect(screen.getByText("Economic calendar")).toBeDefined());
  expect(screen.getByText("NFP")).toBeDefined();
});

test("renders the indicator backdrop section last, with its own freshness line", async () => {
  const indicators = economicIndicators({
    indicators: [{ key: "inflation", label: "Inflation rate", series: "inflationRate",
      value: 2.27, unit: "%", as_of: "2025-11-19", direction: "down", change: -0.23,
      lagging: true }],
  });
  mockApi({ breadth: breadth(), flowEvents: [], indicators });

  renderMacro();

  await waitFor(() => expect(screen.getByText("Growth, inflation & risk backdrop")).toBeDefined());
  expect(screen.getByText("Inflation rate")).toBeDefined();
  expect(screen.getByText("US equity risk premium")).toBeDefined();
});

test("shows a single empty state when every section has nothing, once loading settles", async () => {
  mockApi({
    breadth: null, flowEvents: [], curve: null, calendar: null,
    indicators: null, riskPremium: null,
  });

  renderMacro();

  await waitFor(() => expect(screen.getByText("No macro data yet")).toBeDefined());
  // Only the one composed message — no per-section error/empty boxes.
  expect(screen.queryByText(/no yield curve data yet/)).toBeNull();
  expect(screen.queryByText("Rates & yield curve")).toBeNull();
});

test("a failing yield-curve query does not prevent breadth or the calendar from rendering", async () => {
  const calendar = economicCalendar({
    upcoming: [{ date: "2026-09-04T12:30:00Z", event: "NFP", impact: "High", previous: 3.2, estimate: 3.3, unit: "%" }],
  });
  vi.mocked(api.get).mockImplementation(async (url: string) => {
    if (url === "/market/flow-events") return { data: [] };
    if (url === "/market/breadth") return { data: breadth() };
    if (url === "/market/treasury-curve") throw new Error("network error");
    if (url === "/market/economic-calendar") return { data: calendar };
    if (url === "/market/economic-indicators") return { data: economicIndicators() };
    if (url === "/market/risk-premium") return { data: riskPremium() };
    throw new Error(`unexpected GET ${url}`);
  });

  renderMacro();

  await waitFor(() => expect(screen.getByText("Market breadth")).toBeDefined());
  await waitFor(() => expect(screen.getByText("Economic calendar")).toBeDefined());
  expect(screen.getByText("NFP")).toBeDefined();
  expect(screen.queryByText("Rates & yield curve")).toBeNull();
});

test("a failing economic-calendar query does not prevent the yield curve or indicators from rendering", async () => {
  vi.mocked(api.get).mockImplementation(async (url: string) => {
    if (url === "/market/flow-events") return { data: [] };
    if (url === "/market/breadth") return { data: breadth() };
    if (url === "/market/treasury-curve") return { data: treasuryCurve() };
    if (url === "/market/economic-calendar") throw new Error("network error");
    if (url === "/market/economic-indicators") return { data: economicIndicators() };
    if (url === "/market/risk-premium") return { data: riskPremium() };
    throw new Error(`unexpected GET ${url}`);
  });

  renderMacro();

  await waitFor(() => expect(screen.getByText("Rates & yield curve")).toBeDefined());
  expect(screen.queryByText("Economic calendar")).toBeNull();
});

test("does not show the empty state once at least one section has data", async () => {
  mockApi({
    breadth: null, flowEvents: [], curve: treasuryCurve(), calendar: null,
    indicators: null, riskPremium: null,
  });

  renderMacro();

  await waitFor(() => expect(screen.getByText("Rates & yield curve")).toBeDefined());
  expect(screen.queryByText("No macro data yet")).toBeNull();
});

test("an event older than the active window does not decorate the panel", async () => {
  const stale = flowEvent({
    created_at: new Date(Date.now() - 20 * 24 * 60 * 60 * 1000).toISOString(),
  });
  mockApi({ breadth: breadth(), flowEvents: [stale] });

  renderMacro();

  await waitFor(() => expect(screen.getByText("Market breadth")).toBeDefined());
  expect(screen.queryByText("Breadth divergence detected")).toBeNull();
});

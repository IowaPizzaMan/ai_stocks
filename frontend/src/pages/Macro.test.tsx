import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../api/client";
import type { MacroReads, MarketFlowEvent, SectorMacroRead } from "../api/types";
import Macro from "./Macro";

vi.mock("../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function sectorRead(overrides: Partial<SectorMacroRead> = {}): SectorMacroRead {
  return {
    sector: "Technology",
    computed_at: new Date().toISOString(),
    overall_macro_signal: "neutral",
    confidence: "medium",
    inflation_impact: { trend: "stable", impact_on_sector: "Neutral for margins." },
    rate_impact: { direction: "holding", impact_on_valuation: "Neutral for multiples." },
    growth_backdrop: { recession_signal: "mild", commentary: "Cooling but no recession yet." },
    consumer_backdrop: "Resilient spending.",
    sector_rotation_signal: "Neutral rotation.",
    ...overrides,
  };
}

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

function mockApi({
  sectors = [],
  flowEvents = [],
  breadth = null,
}: {
  sectors?: SectorMacroRead[];
  flowEvents?: MarketFlowEvent[];
  breadth?: unknown;
} = {}) {
  vi.mocked(api.get).mockImplementation(async (url: string) => {
    if (url === "/market/macro") {
      const body: MacroReads = {
        sectors,
        as_of: sectors[0]?.computed_at ?? null,
      };
      return { data: body };
    }
    if (url === "/market/flow-events") return { data: flowEvents };
    if (url === "/market/breadth") return { data: breadth };
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

test("renders one card per sector with its commentary and signal", async () => {
  mockApi({
    sectors: [
      sectorRead({ sector: "Technology", overall_macro_signal: "bullish" }),
      sectorRead({ sector: "Financials", overall_macro_signal: "bearish" }),
    ],
  });

  renderMacro();

  await waitFor(() => expect(screen.getByText("Technology")).toBeDefined());
  expect(screen.getByText("Financials")).toBeDefined();
  expect(screen.getAllByText(/Neutral for margins\./i)).toHaveLength(2);
});

test("shows a freshness indicator on each sector card", async () => {
  mockApi({ sectors: [sectorRead({ sector: "Technology" })] });

  renderMacro();

  await waitFor(() => expect(screen.getByText("Technology")).toBeDefined());
  expect(screen.getAllByText(/just now|ago/i).length).toBeGreaterThan(0);
});

test("still renders a stale sector read with its age visible", async () => {
  const staleDate = new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString();
  mockApi({ sectors: [sectorRead({ sector: "Energy", computed_at: staleDate })] });

  renderMacro();

  await waitFor(() => expect(screen.getByText("Energy")).toBeDefined());
  expect(screen.getAllByText(/\d+d ago/i).length).toBeGreaterThan(0);
});

test("renders pinned market-breadth cards alongside sector reads", async () => {
  mockApi({
    sectors: [sectorRead()],
    flowEvents: [flowEvent({ headline: "Breadth divergence detected" })],
  });

  renderMacro();

  await waitFor(() => expect(screen.getByText("Breadth divergence detected")).toBeDefined());
  expect(screen.getByText("Technology")).toBeDefined();
});

test("shows an empty state with no error when nothing is available yet", async () => {
  mockApi({ sectors: [], flowEvents: [] });

  renderMacro();

  await waitFor(() => expect(screen.getByText(/no macro data yet/i)).toBeDefined());
});

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import type { MarketBreadth, MarketFlowEvent } from "../../api/types";
import MarketFlowCard from "./MarketFlowCard";

afterEach(cleanup);

function flowEvent(overrides: Partial<MarketFlowEvent> = {}): MarketFlowEvent {
  return {
    event_id: "evt-1",
    category: "market_flow",
    kind: "breadth_divergence",
    divergence_type: "bearish",
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

test("with an event: tinted outline, headline, and body render", () => {
  const { container } = render(
    <MarketFlowCard event={flowEvent({ divergence_type: "bearish" })} breadth={breadth()} />,
  );
  expect(screen.getByText("Breadth divergence detected")).toBeDefined();
  expect(screen.getByText(/NYMO diverging from price/)).toBeDefined();
  expect(container.querySelector("article")?.className).toMatch(/border-amber-500/);
});

test("with a bullish event: outline is tinted bullish", () => {
  const { container } = render(
    <MarketFlowCard event={flowEvent({ divergence_type: "bullish" })} breadth={breadth()} />,
  );
  expect(container.querySelector("article")?.className).toMatch(/border-emerald-500/);
});

test("without an event: neutral outline, no headline row, chart still renders", () => {
  const { container } = render(<MarketFlowCard breadth={breadth()} />);
  expect(screen.getByText("Market breadth")).toBeDefined();
  expect(screen.queryByText(/Breadth divergence detected/)).toBeNull();
  expect(screen.queryByText(/NYMO diverging from price/)).toBeNull();
  expect(container.querySelector("article")?.className).toMatch(/border-zinc-800/);
  expect(container.querySelector("article")?.className).not.toMatch(/border-amber-500|border-emerald-500/);
});

test("without an event and no breadth: still renders the neutral card shell", () => {
  render(<MarketFlowCard />);
  expect(screen.getByText("Market breadth")).toBeDefined();
});

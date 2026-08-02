import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

afterEach(cleanup);
import type { InstitutionalFlowEvent } from "../../api/types";
import InstitutionalFlowCard from "./InstitutionalFlowCard";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react-router-dom")>()),
  useNavigate: () => mockNavigate,
}));

const event = (over: Partial<InstitutionalFlowEvent> = {}): InstitutionalFlowEvent => ({
  ticker: "GOOGL",
  fund: "Pershing Square",
  action: "new_position",
  shares: 1_200_000,
  value_usd: 220_000_000,
  pct_of_portfolio: null,
  pct_change: null,
  headline: "Pershing Square opened a new $220M position in GOOGL",
  notability_score: 91,
  source: "13F",
  filed_at: new Date().toISOString(),
  scanned_at: new Date().toISOString(),
  ...over,
});

const renderCard = (e: InstitutionalFlowEvent) =>
  render(
    <MemoryRouter>
      <InstitutionalFlowCard event={e} />
    </MemoryRouter>,
  );

test("renders headline, badge, stats and notability", () => {
  renderCard(event());
  expect(screen.getByText("New Position")).toBeDefined();
  expect(
    screen.getByText("Pershing Square opened a new $220M position in GOOGL"),
  ).toBeDefined();
  expect(screen.getByText("1,200,000 shares")).toBeDefined();
  expect(screen.getByText("$220.0M")).toBeDefined();
  expect(screen.getByText("13F filing")).toBeDefined();
  expect(screen.getByText("Notability 91")).toBeDefined();
});

test("optional numbers are omitted, not rendered as garbage", () => {
  renderCard(
    event({
      shares: null,
      value_usd: null,
      source: "dataroma",
      action: "add",
      headline: "Berkshire Hathaway added to its OXY position",
    }),
  );
  expect(screen.queryByText(/shares/)).toBeNull();
  expect(screen.queryByText(/\$/)).toBeNull();
  expect(screen.getByText("Dataroma")).toBeDefined();
  expect(screen.getByText("Add")).toBeDefined();
});

test("13F pct_change renders as signed QoQ percent", () => {
  renderCard(event({ action: "trim", pct_change: -0.12 }));
  expect(screen.getByText("-12% QoQ")).toBeDefined();
});

test("clicking the ticker navigates to stock detail", () => {
  renderCard(event());
  fireEvent.click(screen.getByText("GOOGL"));
  expect(mockNavigate).toHaveBeenCalledWith("/stock/GOOGL");
});

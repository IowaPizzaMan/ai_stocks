import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import type { Pull } from "../../api/types";
import PullCostPanel from "./PullCostPanel";

afterEach(cleanup);

// Server sorts most-expensive-first (contracts/queue-pull-mode.md), so the
// fixture arrives already ranked — the panel must not re-sort or reverse it.
const pull: Pull = {
  job_id: "j1",
  mode: "delta",
  started_at: "2026-08-17T14:02:11Z",
  completed_at: "2026-08-17T14:02:52Z",
  total_ms: 41230,
  outcome: "done",
  accounted_ms: 38110,
  unaccounted_ms: 3120,
  stages: [
    { name: "news", elapsed_ms: 20000, requests: 3, bytes: 900_000, retrieval: "incremental", outcome: "fetched" },
    { name: "price", elapsed_ms: 12000, requests: 1, bytes: 412_889, retrieval: "incremental", outcome: "fetched" },
    { name: "financials", elapsed_ms: 5000, requests: 7, bytes: 90_000, retrieval: "full", outcome: "fetched" },
    { name: "indicators", elapsed_ms: 1000, requests: 0, bytes: 0, retrieval: "stored", outcome: "stored" },
    { name: "breadth", elapsed_ms: 110, requests: 0, bytes: 0, retrieval: "stored", outcome: "stored" },
  ],
};

test("shows the three most expensive stages without expanding", () => {
  render(<PullCostPanel pull={pull} />);

  // SC-006 — top three readable while collapsed
  expect(screen.getByText("news")).toBeTruthy();
  expect(screen.getByText("price")).toBeTruthy();
  expect(screen.getByText("financials")).toBeTruthy();
  // ranks 4-5 stay hidden until expanded
  expect(screen.queryByText("indicators")).toBeNull();
  expect(screen.queryByText("breadth")).toBeNull();
});

test("preserves the server's cost ranking", () => {
  const { container } = render(<PullCostPanel pull={pull} />);
  const names = Array.from(container.querySelectorAll("[data-stage-name]")).map(
    (el) => el.getAttribute("data-stage-name"),
  );
  expect(names).toEqual(["news", "price", "financials"]);
});

test("expanding reveals every stage", () => {
  render(<PullCostPanel pull={pull} />);
  fireEvent.click(screen.getByRole("button", { name: /pull cost/i }));

  expect(screen.getByText("indicators")).toBeTruthy();
  expect(screen.getByText("breadth")).toBeTruthy();
});

test("labels each stage's retrieval kind so delta savings are visible", () => {
  render(<PullCostPanel pull={pull} />);
  fireEvent.click(screen.getByRole("button", { name: /pull cost/i }));

  // FR-002 — incremental vs full vs served-from-store
  expect(screen.getAllByText(/incremental/i).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/stored/i).length).toBeGreaterThan(0);
});

test("shows the pull mode and outcome", () => {
  render(<PullCostPanel pull={pull} />);
  // FR-028 — a delta pull must be distinguishable from a full refresh
  expect(screen.getByText(/delta/i)).toBeTruthy();
});

test("marks a full refresh distinctly from a delta pull", () => {
  render(<PullCostPanel pull={{ ...pull, mode: "full" }} />);
  expect(screen.getByText(/full refresh/i)).toBeTruthy();
});

test("surfaces a degraded pull rather than showing it as clean", () => {
  render(<PullCostPanel pull={{ ...pull, outcome: "degraded" }} />);
  expect(screen.getByText(/degraded/i)).toBeTruthy();
});

test("shows unaccounted time rather than dropping it", () => {
  render(<PullCostPanel pull={pull} />);
  fireEvent.click(screen.getByRole("button", { name: /pull cost/i }));
  // FR-004 — time the breakdown cannot explain is itself a finding
  expect(screen.getByText(/unaccounted/i)).toBeTruthy();
});

test("renders an empty state when the ticker has never been pulled", () => {
  render(<PullCostPanel pull={null} />);
  expect(screen.getByText(/no pull recorded/i)).toBeTruthy();
});

test("handles a pull that recorded no stages", () => {
  render(<PullCostPanel pull={{ ...pull, stages: [], accounted_ms: 0 }} />);
  expect(screen.getByText(/no stage detail/i)).toBeTruthy();
});

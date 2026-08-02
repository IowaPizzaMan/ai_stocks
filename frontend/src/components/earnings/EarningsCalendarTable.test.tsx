import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

afterEach(cleanup);
import type { EarningsCandidate } from "../../api/types";
import EarningsCalendarTable from "./EarningsCalendarTable";

const candidate = (over: Partial<EarningsCandidate>): EarningsCandidate => ({
  ticker: "TST",
  company: "Test Co",
  report_date: "2026-08-05",
  report_time: "amc",
  sector: "Technology",
  market_cap: 1e9,
  score: 50,
  score_breakdown: { move_pts: 10, beat_pts: 10, revision_pts: 10, insider_pts: 10, accumulation_pts: 10 },
  avg_abs_move_pct: 6.2,
  beat_rate: 0.75,
  history_quarters: 8,
  eps_revision: "flat",
  insider_signal: "none",
  accumulation_score: 2,
  one_line_thesis: "TST: solid setup",
  ...over,
});

const CANDIDATES = [
  candidate({ ticker: "LOW", score: 35 }),
  candidate({ ticker: "HIGH", score: 88, insider_signal: "cluster", eps_revision: "up" }),
];

test("renders candidates sorted by score desc with signals", () => {
  render(
    <EarningsCalendarTable
      candidates={CANDIDATES}
      isLoading={false}
      queuedTickers={new Set()}
      onAnalyzeTicker={() => {}}
      onShowDetails={() => {}}
    />,
  );
  const rows = screen.getAllByRole("row").slice(1); // drop header
  expect(rows[0].textContent).toContain("HIGH");
  expect(rows[1].textContent).toContain("LOW");
  expect(rows[0].textContent).toContain("● Cluster");
  expect(rows[0].textContent).toContain("↑ Up");
  expect(rows[0].textContent).toContain("6/8");
});

test("row click analyzes; queued rows show badge instead", () => {
  const onAnalyze = vi.fn();
  render(
    <EarningsCalendarTable
      candidates={CANDIDATES}
      isLoading={false}
      queuedTickers={new Set(["LOW"])}
      onAnalyzeTicker={onAnalyze}
      onShowDetails={() => {}}
    />,
  );
  fireEvent.click(screen.getByText("HIGH"));
  expect(onAnalyze).toHaveBeenCalledWith("HIGH");
  expect(screen.getByText("Queued")).toBeDefined();
  expect(screen.getAllByText("Analyze ▶")).toHaveLength(1);
});

test("details button opens card without enqueueing", () => {
  const onAnalyze = vi.fn();
  const onDetails = vi.fn();
  render(
    <EarningsCalendarTable
      candidates={[CANDIDATES[1]]}
      isLoading={false}
      queuedTickers={new Set()}
      onAnalyzeTicker={onAnalyze}
      onShowDetails={onDetails}
    />,
  );
  fireEvent.click(screen.getByText("Details"));
  expect(onDetails).toHaveBeenCalledOnce();
  expect(onAnalyze).not.toHaveBeenCalled();
});

test("shows skeleton rows while loading", () => {
  const { container } = render(
    <EarningsCalendarTable
      candidates={[]}
      isLoading={true}
      queuedTickers={new Set()}
      onAnalyzeTicker={() => {}}
      onShowDetails={() => {}}
    />,
  );
  expect(container.querySelectorAll("tr.animate-pulse")).toHaveLength(5);
});

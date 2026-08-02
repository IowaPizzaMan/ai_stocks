import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { EarningsCalendarEntry } from "../../api/types";
import UpcomingEarningsTable, { formatCompact } from "./UpcomingEarningsTable";

afterEach(cleanup);

const ENTRIES: EarningsCalendarEntry[] = [
  {
    ticker: "BIG", company: "Big Co", report_date: "2026-08-04", report_time: "bmo",
    eps_estimate: 1.2345, revenue_estimate: 2.8e9, market_cap: 50e9, sector: "Technology",
  },
  {
    ticker: "MID", company: "Mid Co", report_date: "2026-08-05", report_time: "unknown",
    eps_estimate: null, revenue_estimate: null, market_cap: 8e8, sector: null,
  },
];

test("renders calendar rows with formatted estimates", () => {
  render(
    <UpcomingEarningsTable
      entries={ENTRIES}
      isLoading={false}
      queuedTickers={new Set()}
      onQueueTicker={() => {}}
    />,
  );
  const rows = screen.getAllByRole("row").slice(1);
  expect(rows[0].textContent).toContain("BIG");
  expect(rows[0].textContent).toContain("1.23");
  expect(rows[0].textContent).toContain("$2.8B");
  expect(rows[0].textContent).toContain("$50.0B");
  expect(rows[0].textContent).toContain("bmo");
  expect(rows[1].textContent).toContain("$800M"); // mkt cap; null estimates render —
});

test("queue button enqueues only that ticker; queued rows show badge", () => {
  const onQueue = vi.fn();
  render(
    <UpcomingEarningsTable
      entries={ENTRIES}
      isLoading={false}
      queuedTickers={new Set(["MID"])}
      onQueueTicker={onQueue}
    />,
  );
  const buttons = screen.getAllByText("Queue ▶");
  expect(buttons).toHaveLength(1); // MID already queued
  fireEvent.click(buttons[0]);
  expect(onQueue).toHaveBeenCalledExactlyOnceWith("BIG");
  expect(screen.getByText("Queued")).toBeDefined();
});

test("formatCompact handles magnitudes and nulls", () => {
  expect(formatCompact(null)).toBe("—");
  expect(formatCompact(1.5e12)).toBe("$1.5T");
  expect(formatCompact(2.34e9)).toBe("$2.3B");
  expect(formatCompact(154_286_200)).toBe("$154M");
});

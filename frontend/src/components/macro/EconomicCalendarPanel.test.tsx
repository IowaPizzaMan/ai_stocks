import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import type { EconomicEvent, ReportedEconomicEvent } from "../../api/types";
import EconomicCalendarPanel from "./EconomicCalendarPanel";

afterEach(cleanup);

function upcomingEvent(overrides: Partial<EconomicEvent> = {}): EconomicEvent {
  return {
    date: "2026-09-04T12:30:00Z", event: "Average Hourly Earnings YoY",
    impact: "High", previous: 3.2, estimate: 3.3, unit: "%",
    ...overrides,
  };
}

function reportedEvent(overrides: Partial<ReportedEconomicEvent> = {}): ReportedEconomicEvent {
  return {
    date: "2026-08-19T12:30:00Z", event: "Retail Sales MoM",
    impact: "High", previous: 0.4, estimate: 0.3, unit: "%",
    actual: 0.6, comparison: "above", surprise: 0.3,
    ...overrides,
  };
}

test("renders an upcoming row with its estimate", () => {
  render(<EconomicCalendarPanel upcoming={[upcomingEvent()]} reported={[]} />);
  expect(screen.getByText("Average Hourly Earnings YoY")).toBeDefined();
  expect(screen.getByText(/est\. 3\.3%/)).toBeDefined();
});

test("shows an upcoming event's estimate as explicitly unavailable when null", () => {
  render(<EconomicCalendarPanel upcoming={[upcomingEvent({ estimate: null })]} reported={[]} />);
  expect(screen.getByText(/est\. unavailable/)).toBeDefined();
});

test("empty upcoming list states there are no major releases scheduled", () => {
  render(<EconomicCalendarPanel upcoming={[]} reported={[]} />);
  expect(screen.getByText("No major releases scheduled.")).toBeDefined();
});

test("renders a reported row's actual value and neutral comparison label", () => {
  render(<EconomicCalendarPanel upcoming={[]} reported={[reportedEvent()]} />);
  expect(screen.getByText("Retail Sales MoM")).toBeDefined();
  expect(screen.getByText("above estimate")).toBeDefined();
});

test("comparison labels never imply good or bad — same neutral wording for above and below", () => {
  const { container, rerender } = render(
    <EconomicCalendarPanel upcoming={[]} reported={[reportedEvent({ comparison: "above" })]} />,
  );
  const aboveClass = container.querySelector("li")?.className;

  rerender(
    <EconomicCalendarPanel
      upcoming={[]}
      reported={[reportedEvent({ event: "Retail Sales MoM", comparison: "below" })]}
    />,
  );
  const belowClass = container.querySelector("li")?.className;

  expect(screen.getByText("below estimate")).toBeDefined();
  // no divergent styling by outcome — same class shape regardless of comparison
  expect(aboveClass).toBe(belowClass);
});

test("a reported event with no estimate shows 'no estimate' rather than a fabricated label", () => {
  render(
    <EconomicCalendarPanel
      upcoming={[]}
      reported={[reportedEvent({ estimate: null, comparison: null, surprise: null })]}
    />,
  );
  expect(screen.getByText("no estimate")).toBeDefined();
  expect(screen.queryByText("in line")).toBeNull();
});

test("empty reported list explains nothing has reported yet", () => {
  render(<EconomicCalendarPanel upcoming={[]} reported={[]} />);
  expect(screen.getByText("Nothing has reported in this window yet.")).toBeDefined();
});

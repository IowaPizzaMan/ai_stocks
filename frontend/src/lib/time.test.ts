import { expect, test } from "vitest";
import { formatEasternTime, formatMonthDay } from "./time";

test("formats a date as compact M/D for the activity feed", () => {
  expect(formatMonthDay("2026-09-04T12:30:00Z")).toBe("9/4");
});

test("formatMonthDay returns null for an unparseable timestamp", () => {
  expect(formatMonthDay("not-a-date")).toBeNull();
});

test("formats a UTC instant as US/Eastern with an explicit ET label", () => {
  // 12:30 UTC on 2026-09-04 is 08:30 America/New_York (EDT, UTC-4 in September)
  expect(formatEasternTime("2026-09-04T12:30:00Z")).toBe("Sep 4, 8:30 AM ET");
});

test("returns null for an unparseable timestamp", () => {
  expect(formatEasternTime("not-a-date")).toBeNull();
});

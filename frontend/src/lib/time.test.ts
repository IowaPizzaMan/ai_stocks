import { expect, test } from "vitest";
import { formatEasternTime } from "./time";

test("formats a UTC instant as US/Eastern with an explicit ET label", () => {
  // 12:30 UTC on 2026-09-04 is 08:30 America/New_York (EDT, UTC-4 in September)
  expect(formatEasternTime("2026-09-04T12:30:00Z")).toBe("Sep 4, 8:30 AM ET");
});

test("returns null for an unparseable timestamp", () => {
  expect(formatEasternTime("not-a-date")).toBeNull();
});

import { expect, test } from "vitest";
import type { AnalysisFeedItem } from "../api/types";
import { groupBySignal } from "./groupFeed";

function item(overrides: Partial<AnalysisFeedItem>): AnalysisFeedItem {
  return {
    ticker: "AAA",
    timestamp: "2026-08-15T00:00:00Z",
    signal: "neutral",
    conviction: "medium",
    summary: "",
    key_trends: [],
    flags: [],
    ...overrides,
  } as AnalysisFeedItem;
}

test("groups appear in fixed order: bullish, neutral, bearish", () => {
  const items = [
    item({ ticker: "BEAR", signal: "bearish" }),
    item({ ticker: "NEUT", signal: "neutral" }),
    item({ ticker: "BULL", signal: "bullish" }),
  ];

  const groups = groupBySignal(items);

  expect(groups.map((g) => g.signal)).toEqual(["bullish", "neutral", "bearish"]);
});

test("sorts items within a group newest-first by timestamp", () => {
  const items = [
    item({ ticker: "OLD", signal: "bullish", timestamp: "2026-08-01T00:00:00Z" }),
    item({ ticker: "NEW", signal: "bullish", timestamp: "2026-08-10T00:00:00Z" }),
    item({ ticker: "MID", signal: "bullish", timestamp: "2026-08-05T00:00:00Z" }),
  ];

  const groups = groupBySignal(items);

  expect(groups[0].items.map((i) => i.ticker)).toEqual(["NEW", "MID", "OLD"]);
});

test("buckets unrecognized or missing signals into a trailing 'unknown' group", () => {
  const items = [
    item({ ticker: "GOOD", signal: "bullish" }),
    item({ ticker: "BAD", signal: "not-a-signal" as AnalysisFeedItem["signal"] }),
    item({ ticker: "MISSING", signal: undefined as unknown as AnalysisFeedItem["signal"] }),
  ];

  const groups = groupBySignal(items);

  expect(groups.map((g) => g.signal)).toEqual(["bullish", "unknown"]);
  expect(groups.find((g) => g.signal === "unknown")?.items.map((i) => i.ticker)).toEqual([
    "BAD",
    "MISSING",
  ]);
});

test("omits empty groups entirely rather than rendering them blank", () => {
  const items = [item({ ticker: "ONLY", signal: "bearish" })];

  const groups = groupBySignal(items);

  expect(groups).toEqual([{ signal: "bearish", items: [items[0]] }]);
});

test("returns an empty array for empty input", () => {
  expect(groupBySignal([])).toEqual([]);
});

test("is a pure function: identical input produces identical output", () => {
  const items = [item({ ticker: "A", signal: "bullish" }), item({ ticker: "B", signal: "bearish" })];

  expect(groupBySignal(items)).toEqual(groupBySignal(items));
});

test("regrouping a larger merged array places later-loaded items into their correct existing group (page-merge behavior)", () => {
  const firstPage = [
    item({ ticker: "B1", signal: "bullish", timestamp: "2026-08-10T00:00:00Z" }),
    item({ ticker: "N1", signal: "neutral", timestamp: "2026-08-09T00:00:00Z" }),
  ];
  const merged = [
    ...firstPage,
    item({ ticker: "B2", signal: "bullish", timestamp: "2026-08-12T00:00:00Z" }), // newer, same group
    item({ ticker: "R1", signal: "bearish", timestamp: "2026-08-01T00:00:00Z" }), // new group appears
  ];

  const groups = groupBySignal(merged);

  expect(groups.map((g) => g.signal)).toEqual(["bullish", "neutral", "bearish"]);
  const bullish = groups.find((g) => g.signal === "bullish")!;
  expect(bullish.items.map((i) => i.ticker)).toEqual(["B2", "B1"]);
});

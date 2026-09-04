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

// 037-stocks-conviction-and-activity (contracts/feed-ordering.md #7): the
// server now returns items pre-ordered (conviction desc, ticker asc) — a
// total order given analyses' unique ticker index — so grouping must
// preserve that order verbatim, never re-sort by timestamp or anything else.
test("preserves the server-provided order within a group, not timestamp order", () => {
  const items = [
    item({ ticker: "AVB", signal: "bullish", conviction: "high", timestamp: "2026-08-01T00:00:00Z" }),
    item({ ticker: "MSFT", signal: "bullish", conviction: "high", timestamp: "2026-08-10T00:00:00Z" }),
    item({ ticker: "GOOG", signal: "bullish", conviction: "medium", timestamp: "2026-08-05T00:00:00Z" }),
  ];

  const groups = groupBySignal(items);

  // input order preserved exactly, even though it is NOT timestamp order
  expect(groups[0].items.map((i) => i.ticker)).toEqual(["AVB", "MSFT", "GOOG"]);
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

test("regrouping a larger merged array places later-loaded items into their correct existing group without reindexing earlier ones (Load more / FR-003)", () => {
  const firstPage = [
    item({ ticker: "B1", signal: "bullish", conviction: "high" }),
    item({ ticker: "N1", signal: "neutral", conviction: "high" }),
  ];
  const merged = [
    ...firstPage,
    // "Load more" appends items that sort AFTER the last-shown one — here a
    // same-group, lower-conviction ticker, and a brand-new group appearing.
    item({ ticker: "B2", signal: "bullish", conviction: "low" }),
    item({ ticker: "R1", signal: "bearish", conviction: "high" }),
  ];

  const groups = groupBySignal(merged);

  expect(groups.map((g) => g.signal)).toEqual(["bullish", "neutral", "bearish"]);
  const bullish = groups.find((g) => g.signal === "bullish")!;
  // B1 keeps its position — appending B2 never reorders it (no reflow)
  expect(bullish.items.map((i) => i.ticker)).toEqual(["B1", "B2"]);
});

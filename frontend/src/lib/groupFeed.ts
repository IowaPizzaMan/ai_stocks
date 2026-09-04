import type { AnalysisFeedItem, Signal } from "../api/types";

export type FeedGroupSignal = Signal | "unknown";

export interface FeedGroup {
  signal: FeedGroupSignal;
  items: AnalysisFeedItem[];
}

export type GroupedFeed = FeedGroup[];

// Fixed board order: strongest-to-weakest sentiment, unrecognized data last
// (never silently folded into "neutral" — see spec edge case).
const GROUP_ORDER: FeedGroupSignal[] = ["bullish", "neutral", "bearish", "unknown"];
const KNOWN_SIGNALS = new Set<Signal>(["bullish", "bearish", "neutral"]);

function bucketFor(signal: AnalysisFeedItem["signal"]): FeedGroupSignal {
  return KNOWN_SIGNALS.has(signal as Signal) ? (signal as Signal) : "unknown";
}

/**
 * Groups feed items by signal for the checkerboard grid. Pure and stateless —
 * called with the full flattened item list on every render, so pages merging
 * in via infinite scroll land in their correct group automatically.
 *
 * specs/037-stocks-conviction-and-activity (contracts/feed-ordering.md): each
 * bucket's items are left in the order the server returned them —
 * conviction descending, then ticker ascending, a *total* order over the
 * whole feed (analyses has a unique index on ticker). A signal-group subset
 * of a total order is itself ordered, so grouping never needs to re-sort.
 * Previously this re-sorted each bucket by timestamp descending; that would
 * now undo the server's order on every render and make "Load more" reflow
 * already-rendered tiles (FR-003) — do not reintroduce a client-side sort
 * here.
 */
export function groupBySignal(items: AnalysisFeedItem[]): GroupedFeed {
  const buckets = new Map<FeedGroupSignal, AnalysisFeedItem[]>();

  for (const item of items) {
    const key = bucketFor(item.signal);
    const bucket = buckets.get(key);
    if (bucket) bucket.push(item);
    else buckets.set(key, [item]);
  }

  return GROUP_ORDER.filter((signal) => buckets.has(signal)).map((signal) => ({
    signal,
    items: buckets.get(signal)!,
  }));
}

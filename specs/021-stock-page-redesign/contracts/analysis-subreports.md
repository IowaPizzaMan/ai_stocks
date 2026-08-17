# Contract: Analysis Document Extensions

The analysis document written by `agent-runner/crew.py` and served untouched by `backend/routers/analysis.py` gains one new sub-report, two sub-report extensions, and one new top-level field. Frontend `api/types.ts` mirrors these exactly (Principle VI). Field-level shapes: [data-model.md](../data-model.md).

## New: `sub_reports.news`

```ts
interface NewsReport {
  articles: {
    date: string;            // ISO date
    datetime: string;        // full published timestamp
    source: string;
    headline: string;
    url: string;
    text_excerpt: string;
    bullish_count: number;
    bearish_count: number;
    ai_summary: string | null;   // 15 newest articles only
  }[];                           // newest first, full 30-day window
  timeline: { date: string; bullish: number; bearish: number; article_count: number }[]; // ascending
  trend: "bullish" | "bearish" | "mixed";
  stance: { direction: "bullish" | "neutral" | "bearish"; reasoning: string } | null;
  news_count: number;
  days_covered: number;          // dates in the window that had coverage
  window_days: number;           // window requested (30)
  as_of: string | null;
}
```

Producer: `tools/news.py` (fetch + deterministic counts/timeline/trend) → `agents/news_analyst.py` (summaries + stance). Consumers: News tab (all), Sentiment tab (`timeline`, `trend`), AI Summary (`stance`).

## Extended: `sub_reports.insider`

Adds `quarterly_stats: InsiderQuarterStats[]` (see data-model §4; from FMP `insider-trading/statistics`, newest first, ≤ 8 quarters). All existing fields unchanged. Consumers: Insider tab flow charts. Absent/empty array = FMP unavailable → UI falls back to existing content plus empty-state note.

## Extended: `sub_reports.institutional`

Adds:
- `beneficial_filings: BeneficialFiling[]` (data-model §5, newest first, ≤ 20)
- `beneficial_direction: "accumulating" | "distributing" | "mixed" | null`

All existing fields unchanged (including `institutional_summary` from the stale cached snapshot). Consumers: Institutional tab visuals + net verdict.

## New top-level: `changes_since_last`

```ts
interface ChangesSinceLast {
  previous_timestamp: string;
  signal: { from: string; to: string; changed: boolean };
  conviction: { from: string; to: string; changed: boolean };
  flags_added: string[];
  flags_removed: string[];
}
// optional on Analysis — absent on first-ever pulls
```

Producer: pure diff function in `crew.py` (pytest-covered). Consumer: AI Summary tab.

## Compatibility rules

- Every new field is **optional** on read: analyses stored before 021 lack them all, and every consuming component must render sensibly (hide section / empty state) when they're absent. RTL tests assert this for each tab.
- No existing field is renamed, moved, or removed. `position_management` remains in the document (Overview simply stops rendering it).
- `sub_reports.recommendation` unchanged; AI Summary keeps rendering its `caveats` while dropping the breadth chart.

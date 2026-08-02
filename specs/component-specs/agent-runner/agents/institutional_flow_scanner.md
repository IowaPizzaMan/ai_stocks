# agent-runner/agents/institutional_flow_scanner.md

## Purpose
Market-wide counterpart to `institutional_analyst.md`. Where `InstitutionalAnalyst` answers "what is smart money doing in **this ticker**?" as one step of a per-ticker crew run, `InstitutionalFlowScannerAgent` answers "what did smart money do **today, across everything**?" It is not parameterized by `{ticker}` — it sweeps all recent 13F changes and Dataroma superinvestor moves and emits a stream of discrete, feed-ready events. This is what powers the Institutional Flow page.

## Relationship to InstitutionalAnalyst
| | `InstitutionalAnalyst` | `InstitutionalFlowScannerAgent` |
|---|---|---|
| Scope | Single ticker | Entire tracked universe |
| Trigger | Part of the per-ticker crew (`crew.py`), runs when a ticker is queued | Standalone scheduled scan, independent of `work_queue` |
| Output | One JSON blob appended to that ticker's `analyses` document | Many small `institutional_flow` event documents, one per move |
| Consumed by | Stock Detail → Institutional tab | Institutional Flow page (feed) |

They share the same underlying data sources and can share tooling — this agent just widens the lens from one ticker to all of them and reshapes the output for a feed instead of a report.

## CrewAI Agent Definition

```python
Agent(
    role="Institutional Flow Scanner",
    goal="Surface every notable institutional and superinvestor move across the tracked universe since the last scan, ranked by how much it should matter to the user",
    backstory="You watch 13F filings and superinvestor portfolio changes the moment they post, across every ticker — not just one. You separate real conviction signals (concentrated funds opening or exiting large positions) from noise (passive index rebalancing, tiny trims).",
    tools=[get_recent_13f_changes, get_recent_superinvestor_moves],
    llm=llm,
    allow_delegation=False
)
```

## Task Prompt
```
You are given raw institutional filing and superinvestor move data collected since the last scan
(timestamp: {since}). For each distinct move:

1. Identify: fund name, ticker, action (new_position | add | trim | exit), shares/value, % of fund's portfolio if known.
2. Classify notability: is this a concentrated high-conviction fund (e.g. Pershing Square, Berkshire,
   a Dataroma-tracked superinvestor) or a passive/index vehicle? Passive-only moves are low notability.
3. Write a one-sentence, feed-readable headline for the move (e.g. "Pershing Square opened a new
   $220M position in GOOGL").
4. Assign a notability score 0-100 so the feed can rank/highlight the most important moves first.

Do not summarize across tickers — emit one structured event per move, not an aggregate report.

Return a JSON array of events: fund, ticker, action, shares, value_usd, pct_of_portfolio,
headline, notability_score, source ("13F" | "dataroma"), filed_at.
```

## Data Sources
- FMP `v3/institutional-holder` / `v3/form-thirteen`, scanned across the tracked universe (watchlist ∪ any ticker with a prior analysis) rather than one ticker at a time
- `tools/superinvestor.py` — Dataroma `moves.php`, which is already global (not ticker-scoped); this agent just consumes it directly instead of filtering to one ticker
- Fallback: SEC EDGAR full-text search for 13F-HR filings dated since the last scan

## Trigger & Schedule
Runs independently of the per-ticker `work_queue` — see `institutional_flow_worker.md`. Scheduled once daily after market close by default; can also be triggered on demand via `POST /institutional/scan`.

## Output Shape
Emits a JSON array (one element per move), each written as its own document in the `institutional_flow` collection:

```json
[
  {
    "fund": "Pershing Square",
    "ticker": "GOOGL",
    "action": "new_position",
    "shares": 1200000,
    "value_usd": 220000000,
    "pct_of_portfolio": 8.4,
    "headline": "Pershing Square opened a new $220M position in GOOGL",
    "notability_score": 91,
    "source": "13F",
    "filed_at": "2026-07-30T00:00:00Z",
    "scanned_at": "2026-08-01T04:00:00Z"
  },
  {
    "fund": "Berkshire Hathaway",
    "ticker": "OXY",
    "action": "add",
    "shares": 2000000,
    "value_usd": 130000000,
    "pct_of_portfolio": 2.1,
    "headline": "Berkshire Hathaway added 2M shares of OXY",
    "notability_score": 84,
    "source": "dataroma",
    "filed_at": "2026-07-29T00:00:00Z",
    "scanned_at": "2026-08-01T04:00:00Z"
  }
]
```

# agent-runner/agents/earnings_scanner.py

## Purpose
Scores and ranks upcoming earnings candidates. Runs during the calendar sweep phase — before any full crew analysis. Produces a ranked list of tickers with score breakdown for the user to review.

## CrewAI Agent Definition

```python
Agent(
    role="Earnings Calendar Scanner",
    goal="Score and rank companies reporting earnings in the next {days_ahead} days by their potential as an earnings play",
    backstory="You analyze upcoming earnings events to find the highest-potential setups. You look for companies with a history of large post-earnings moves, analysts raising estimates into the print, and insider buying in the weeks before — signals that suggest conviction ahead of a catalyst.",
    tools=[get_earnings_calendar, get_earnings_history, get_insider_activity, get_accumulation_score, get_eps_revisions],
    llm=llm,
    allow_delegation=False
)
```

## Task Prompt

```
Scan the earnings calendar for the next {days_ahead} days and identify the best setups.

For each candidate in the pre-screened list:
1. Fetch earnings history: avg absolute post-earnings move, beat rate, consistency.
2. Check EPS revision trend (last 30 days): analysts raising or lowering estimates?
3. Quick insider check: any open-market purchases in the last 60 days?
4. Quick accumulation score: run the accumulation skill on 30-day volume data.
5. Compute a composite score (0-100) using the scoring weights below.

Scoring weights:
- avg_abs_move_pct (normalized, cap at 15%): 25 pts
- beat_rate (last 8 quarters): 20 pts
- eps_revision_direction (up=20, flat=10, down=0): 20 pts
- insider_activity (cluster=20, single=10, none=0): 20 pts
- accumulation_score (0-5 → 0-15 pts): 15 pts

Return a ranked list, highest score first. For each:
{
  "ticker": str,
  "company": str,
  "report_date": str,
  "report_time": "bmo"|"amc"|"unknown",
  "sector": str,
  "score": int (0-100),
  "score_breakdown": { each component },
  "avg_abs_move_pct": float,
  "beat_rate": float,
  "eps_revision": "up"|"flat"|"down",
  "insider_signal": "cluster"|"single"|"none",
  "accumulation_score": int,
  "one_line_thesis": str   ← written by LLM, e.g. "NVDA: 9.2% avg move, analysts raised 3 of 4 weeks, CEO bought $1M"
}
```

## Parallelism
The ticker-level data fetching (history, insider, accumulation) runs in parallel across all candidates using `ThreadPoolExecutor` before being handed to the LLM for synthesis:

```python
def score_all_candidates(candidates: list[dict]) -> list[dict]:
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = { c["ticker"]: pool.submit(_fetch_candidate_data, c) for c in candidates }
        enriched = []
        for ticker, future in futures.items():
            try:
                enriched.append(future.result(timeout=30))
            except Exception as e:
                log.warning(f"Failed to fetch data for {ticker}: {e}")
    return enriched
```

## Output (stored in MongoDB `earnings_scans` collection)
```json
{
  "scan_id": "uuid",
  "scan_date": "2025-01-20",
  "days_ahead": 7,
  "status": "complete",
  "candidates": [ ...ranked list... ],
  "total_screened": 47,
  "top_count": 10
}
```

## Performance
- Pre-screen typically cuts the calendar from 50–200 companies down to 20–40 viable candidates
- Parallel fetching: ~30 candidates × 3 API calls each = ~90 calls, run in parallel across 8 workers → ~15–20 seconds total
- LLM scoring synthesis: ~5–10 seconds (short prompt, just scoring)
- Total wall time for a scan: ~30–45 seconds

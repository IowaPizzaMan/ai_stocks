# agent-runner/crew.py

## Purpose
Assembles and runs the full CrewAI multi-agent pipeline for a single ticker. This is where all agents and tools are wired together, execution order is defined, and results are collected and written to MongoDB.

## Class: `Crew`

### `__init__(db)`
- Receives the live MongoDB database handle
- Instantiates all tool modules (price, financials, macro, insider, institutional, superinvestor, sentiment, breadth, db_tools)
- Binds tools to agents

### `run(ticker: str, parallel_prefetch: bool = False) -> dict`
Main entry point called by QueueWorker. Returns the full synthesis result.

The `parallel_prefetch` flag is set to `True` when the job originates from the earnings scanner — in that case all data sources are fetched concurrently before agents run, cutting wall time from ~60s to ~15s.

**Execution flow:**

```
0. Ticker validity check (fast, before any expensive fetching):

   is_valid = price_tool.is_ticker_valid(ticker)
   if not is_valid:
       # Give financials one chance to disagree before concluding it's delisted —
       # a single flaky source shouldn't flip a ticker to removed_from_market.
       financials = financials_tool.get_financials(ticker)
       if not financials or not financials.get("income_statements"):
           raise TickerDelistedError(ticker)
       # else: yfinance hiccup, financials still resolve — proceed normally

1. Data pre-fetch phase:
   
   If parallel_prefetch=True (earnings scanner handoff):
     → ThreadPoolExecutor(max_workers=6), all sources fetched simultaneously
     → Wall time: ~15s (bottlenecked by slowest source)
   
   If parallel_prefetch=False (standard watchlist job):
     → Sequential fetching (simpler, avoids rate-limit spikes)
     → Wall time: ~50-60s
   
   Sources fetched:
   - price_tool.get_price_history(ticker)
   - financials_tool.get_financials(ticker)
   - insider_tool.get_insider_activity(ticker)
   - institutional_tool.get_institutional_holdings(ticker)
   - superinvestor_tool.get_superinvestor_activity(ticker)
   - sentiment_tool.get_earnings_sentiment(ticker)
   - breadth_tool.get_market_breadth()
   - macro_tool.get_macro_data() [shared across all tickers, cache for session]
   
   Parallel implementation:
   ```python
   from concurrent.futures import ThreadPoolExecutor
   
   def _prefetch_parallel(self, ticker: str) -> dict:
       with ThreadPoolExecutor(max_workers=6) as pool:
           futures = {
               "price":         pool.submit(self.price_tool.get_price_history, ticker),
               "financials":    pool.submit(self.financials_tool.get_financials, ticker),
               "insider":       pool.submit(self.insider_tool.get_insider_activity, ticker),
               "institutional": pool.submit(self.institutional_tool.get_institutional_holdings, ticker),
               "sentiment":     pool.submit(self.sentiment_tool.get_earnings_sentiment, ticker),
               "breadth":       pool.submit(self.breadth_tool.get_market_breadth),
           }
           return { key: f.result(timeout=45) for key, f in futures.items() }
   ```

2. Chunker / summarizer phase:
   - Each raw payload passes through chunker.chunk() then summarizer.summarize()
   - Result: compact structured context blocks per domain

3. Agent execution (sequential, each reads summarized context):
   TechnicalAnalyst  → sub_report["technical"]
   FundamentalAnalyst → sub_report["fundamental"]
   MacroAnalyst       → sub_report["macro"]
   InsiderAnalyst     → sub_report["insider"]
   InstitutionalAnalyst → sub_report["institutional"]
   SentimentAnalyst   → sub_report["sentiment"]
   RecommenderAgent   → sub_report["recommendation"]
   PortfolioStrategist (reads all sub_reports) → synthesis

4. Write to MongoDB:
   - analyses collection: { ticker, timestamp, synthesis, sub_reports }
   - Update work_queue job to "done"
```

## `TickerDelistedError`
Raised from the validity check above, before any agents run — no point spending ~50-60s of LLM time analyzing a ticker with no data. Defined alongside `Crew` and imported by `queue_worker.py`, which catches it specifically to distinguish "this ticker is gone" from an ordinary transient failure (network error, rate limit, malformed API response).

```python
class TickerDelistedError(Exception):
    def __init__(self, ticker: str):
        self.ticker = ticker
        super().__init__(f"{ticker}: no price or financials data available — likely delisted or ticker changed")
```

## CrewAI Configuration
- **Process**: `Process.sequential` — agents run in order, each can read prior outputs
- **Verbose**: `False` in production; configurable via env var `CREWAI_VERBOSE=1`
- **LLM**: `Ollama(model=os.getenv("OLLAMA_MODEL", "mistral:7b"), base_url=OLLAMA_URL)`
- Each agent has `allow_delegation=False` — no agent can hand off to another mid-run

## Output Schema (written to `analyses` collection)

```json
{
  "ticker": "AAPL",
  "timestamp": ISODate,
  "signal": "bullish" | "bearish" | "neutral",
  "conviction": "high" | "medium" | "low",
  "summary": "One paragraph synthesis",
  "key_trends": ["trend 1", "trend 2"],
  "flags": ["flag 1"],
  "sub_reports": {
    "technical": { ... },
    "fundamental": { ... },
    "macro": { ... },
    "insider": { ... },
    "institutional": { ... },
    "sentiment": { ... },
    "recommendation": { ... }
  }
}
```

## Dependencies
- `crewai` — `Agent`, `Task`, `Crew`, `Process`
- `langchain_ollama` — `OllamaLLM`
- All agent modules from `agents/`
- All tool modules from `tools/`
- `chunker/chunker.py`, `chunker/summarizer.py`

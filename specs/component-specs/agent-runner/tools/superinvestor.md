# agent-runner/tools/superinvestor.py

## Purpose
Scrapes Dataroma using Playwright (headless Chromium) to fetch superinvestor portfolio data. Site requires JS rendering — raw HTTP won't work. Raw page text is passed to Ollama for structured JSON extraction rather than relying on brittle CSS selectors.

## Strategy: No Hardcoded Selectors
Rather than CSS/XPath selectors that break with site changes, navigate to the page, extract all visible text, and ask Ollama to parse it. Resilient to layout changes.

## Functions

### `get_superinvestor_activity(ticker: str) -> dict`

```python
from playwright.sync_api import sync_playwright

def get_superinvestor_activity(ticker: str) -> dict:
    # Check incremental cache — last pull timestamp
    last_pull = db.dataroma_meta.find_one({ "key": "last_pull" })
    last_date = last_pull["date"] if last_pull else "2020-01-01"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Fetch recent moves since last pull
        page.goto(f"https://dataroma.com/m/moves.php?date={last_date}", wait_until="networkidle")
        moves_text = page.inner_text("body")
        
        # Fetch ticker-specific holdings (overlap page or search)
        page.goto(f"https://dataroma.com/m/overlap.php", wait_until="networkidle")
        overlap_text = page.inner_text("body")
        
        browser.close()
    
    # Use Ollama to extract structured data from raw text
    moves = ollama_extract(moves_text, schema="superinvestor_moves", ticker=ticker)
    overlap = ollama_extract(overlap_text, schema="superinvestor_overlap", ticker=ticker)
    
    # Update last pull timestamp
    db.dataroma_meta.replace_one({ "key": "last_pull" }, { "key": "last_pull", "date": today() }, upsert=True)
    
    return { "moves": moves, "overlap": overlap }
```

### `get_recent_superinvestor_moves(since: datetime) -> list[dict]`
Market-wide variant used by `InstitutionalFlowScannerAgent` (`institutional_flow_scanner.md`) — not scoped to a single ticker. `moves.php` is already a global "everything that changed" feed, so this just extracts it without filtering to one `ticker`.

```python
def get_recent_superinvestor_moves(since: datetime) -> list[dict]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"https://dataroma.com/m/moves.php?date={since.date()}", wait_until="networkidle")
        moves_text = page.inner_text("body")
        browser.close()

    # Ask Ollama to extract every move on the page as a list, not one ticker's moves
    return ollama_extract_list(moves_text, schema="superinvestor_move_list")
```

### `ollama_extract(text: str, schema: str, ticker: str) -> dict`
Calls local Ollama with a structured extraction prompt. Returns parsed JSON.

```python
def ollama_extract(text: str, schema: str, ticker: str) -> dict:
    prompt = f"""
    Extract information about {ticker} from the following Dataroma page text.
    Return only valid JSON with this structure: {SCHEMAS[schema]}
    
    Page text:
    {text[:8000]}  # truncate to avoid context overflow
    """
    response = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": prompt}])
    return json.loads(response["message"]["content"])
```

## Rate Limit / Politeness
- Sleep 2–3 seconds between Playwright requests (random jitter)
- Only fetch moves since last pull (incremental) — not the full site on every run
- Full portfolio re-fetch (`holdings.php`) only monthly or when new fund detected

## Dependencies
- `playwright` (must be installed + `playwright install chromium`)
- `ollama` Python client
- `pymongo`

## Used By
- `agents/institutional_analyst.md` (`get_superinvestor_activity`, per-ticker)
- `agents/institutional_flow_scanner.md` (`get_recent_superinvestor_moves`, market-wide)

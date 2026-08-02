# agent-runner/chunker/chunker.py + summarizer.py

## Purpose
Pre-processes large data payloads before they reach agents. Raw API responses — especially transcripts, full financial histories, and news feeds — can easily exceed an LLM's context window. The chunker splits, the summarizer compresses each chunk, and the results are merged into a compact structured context block.

---

## chunker.py

### `chunk(data: dict | list | str, domain: str, max_tokens: int = 2000) -> list[str]`

Splits a payload into token-safe chunks. `domain` controls how splitting is done:

| Domain | Splitting Strategy |
|---|---|
| `transcript` | Split by speaker turn or paragraph. Keep CEO/CFO speeches intact. |
| `financials` | Split by statement type (income, balance, cashflow). Each is a separate chunk. |
| `news` | Split by article. Group articles by 5 per chunk. |
| `insider` | No splitting needed — transaction lists are small. Pass through. |
| `price_history` | Downsample to last 60 bars (daily), all weekly, last 24 monthly. |

```python
def chunk(data, domain: str, max_tokens: int = 2000) -> list[str]:
    if domain == "transcript":
        return _chunk_transcript(data, max_tokens)
    elif domain == "financials":
        return _chunk_financials(data)
    elif domain == "news":
        return _chunk_news(data, max_tokens)
    else:
        # Generic: serialize to JSON string, split by character count
        raw = json.dumps(data)
        chunk_size = max_tokens * 4  # ~4 chars per token estimate
        return [raw[i:i+chunk_size] for i in range(0, len(raw), chunk_size)]
```

---

## summarizer.py

### `summarize(chunks: list[str], domain: str, ticker: str) -> str`

Summarizes each chunk via Ollama and merges summaries into a single context block.

```python
def summarize(chunks: list[str], domain: str, ticker: str) -> str:
    summaries = []
    for chunk in chunks:
        prompt = SUMMARY_PROMPTS[domain].format(ticker=ticker, chunk=chunk)
        response = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": prompt}])
        summaries.append(response["message"]["content"])
    
    if len(summaries) == 1:
        return summaries[0]
    
    # Merge: ask Ollama to synthesize multiple chunk summaries into one
    merge_prompt = f"Merge these {domain} summaries for {ticker} into a single coherent summary:\n\n" + "\n\n---\n\n".join(summaries)
    merged = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": merge_prompt}])
    return merged["message"]["content"]
```

### Summary Prompt Templates (per domain)

```python
SUMMARY_PROMPTS = {
    "transcript": "Summarize the key statements from this earnings call segment for {ticker}. Focus on: revenue/earnings outlook, guidance, macro commentary, management tone. Be concise.\n\n{chunk}",
    "financials": "Extract the key financial metrics from this {ticker} financial data. Include: revenue growth YoY, margin trends, FCF, key ratios. Return as structured bullet points.\n\n{chunk}",
    "news": "Summarize these news articles about {ticker}. Extract: key events, market reactions, analyst commentary. One sentence per article.\n\n{chunk}",
    "insider": "Summarize insider trading activity for {ticker}: who bought/sold, amounts, timing, and any cluster patterns.\n\n{chunk}",
}
```

## Output
The final merged summary string is what gets passed to each CrewAI agent's task context. It's compact (typically 500–1500 tokens) but contains all the signal — not raw data.

## Dependencies
- `ollama`
- `json`
- `tiktoken` (optional, for precise token counting; fall back to char estimate)

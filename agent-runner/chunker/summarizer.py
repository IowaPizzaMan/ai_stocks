"""Summarizes chunks via Ollama and merges into one compact context block.
Spec: specs/component-specs/agent-runner/chunker.md
"""
from llm import generate_text

SUMMARY_PROMPTS = {
    "transcript": (
        "Summarize the key statements from this earnings call segment for {ticker}. "
        "Focus on: revenue/earnings outlook, guidance, macro commentary, management tone. "
        "Be concise.\n\n{chunk}"
    ),
    "financials": (
        "Extract the key financial metrics from this {ticker} financial data. Include: "
        "revenue growth YoY, margin trends, FCF, key ratios. Return as structured bullet "
        "points.\n\n{chunk}"
    ),
    "news": (
        "Summarize these news articles about {ticker}. Extract: key events, market "
        "reactions, analyst commentary. One sentence per article.\n\n{chunk}"
    ),
    "insider": (
        "Summarize insider trading activity for {ticker}: who bought/sold, amounts, "
        "timing, and any cluster patterns.\n\n{chunk}"
    ),
}
GENERIC_PROMPT = "Summarize this {ticker} data concisely, keeping every number that matters:\n\n{chunk}"


def summarize(chunks: list[str], domain: str, ticker: str, client=None) -> str:
    template = SUMMARY_PROMPTS.get(domain, GENERIC_PROMPT)
    summaries = [
        generate_text(template.format(ticker=ticker, chunk=c), client=client)
        for c in chunks if c.strip()
    ]
    if not summaries:
        return ""
    if len(summaries) == 1:
        return summaries[0]

    merge_prompt = (
        f"Merge these {domain} summaries for {ticker} into a single coherent summary. "
        "Keep every concrete number and named person/fund:\n\n"
        + "\n\n---\n\n".join(summaries)
    )
    return generate_text(merge_prompt, client=client)

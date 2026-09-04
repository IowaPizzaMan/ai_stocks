"""Pure ticker/citation markdown rewriting for chat answers.
Spec: specs/035-chat-and-news-upgrade; research.md R5 (FR-013, FR-014, FR-008).

Deliberately no model calls and no I/O (constitution Principle III) — the LLM
is never trusted to decide what counts as a real ticker (it would invent links
for lookalikes, FR-014's exact failure mode). `linkify_tickers()` runs
backend-side, after the answer text is generated, against the known-ticker
universe read from `screener`.
"""
import re

# Matches: a fenced code block, an inline code span, an existing markdown
# link, or a bare word — in that priority order, so code/links are recognized
# and skipped whole rather than having their contents matched individually.
_TOKEN_RE = re.compile(
    r"(?P<fence>```.*?```)"
    r"|(?P<code>`[^`]*`)"
    r"|(?P<link>\[[^\]]*\]\([^)]*\))"
    r"|(?P<word>[A-Za-z]+)",
    re.DOTALL,
)


def linkify_tickers(text: str, known_tickers: set[str]) -> str:
    """Rewrites bare mentions of a known ticker into `[TICKER](/stock/TICKER)`
    markdown. Matching is case-sensitive against the ticker's own (uppercase)
    form, and skips text already inside a markdown link or a code span/block
    — see backend/tests/test_linkify.py for the exact cases this guarantees.
    """
    if not text or not known_tickers:
        return text

    def _replace(match: re.Match) -> str:
        word = match.group("word")
        if word is not None and word in known_tickers:
            return f"[{word}](/stock/{word})"
        return match.group(0)

    return _TOKEN_RE.sub(_replace, text)


def linkify_citation(title: str, url: str) -> str:
    """Renders a stored news story as a markdown link — the same clickable
    treatment as a ticker (FR-008 tying to FR-013)."""
    return f"[{title}]({url})"

"""Pure ticker/citation markdown rewriting for chat answers.
Spec: specs/035-chat-and-news-upgrade; research.md R5 (FR-013, FR-014, FR-008).

No model calls, no I/O — deterministic text rewriting only (constitution
Principle III), which is what makes the "never link a lookalike" guarantee
(FR-014) exhaustively testable without the LLM in the loop.
"""
from semantic.linkify import linkify_citation, linkify_tickers


def test_a_known_ticker_becomes_a_markdown_link():
    result = linkify_tickers("NVDA rose 3% today.", {"NVDA", "AAPL"})
    assert result == "[NVDA](/stock/NVDA) rose 3% today."


def test_multiple_known_tickers_are_all_linked():
    result = linkify_tickers("AAPL and NVDA both closed higher.", {"AAPL", "NVDA"})
    assert result == "[AAPL](/stock/AAPL) and [NVDA](/stock/NVDA) both closed higher."


def test_a_ticker_not_in_the_known_set_is_left_alone():
    result = linkify_tickers("ZZZZ is not a real ticker.", {"AAPL"})
    assert result == "ZZZZ is not a real ticker."


def test_lowercase_prose_words_that_collide_with_tickers_are_not_linked():
    # "IT", "ALL", "ON", "A" are plausible tickers but the match must be
    # case-sensitive so ordinary lowercase prose is never mistaken for one.
    text = "it was on the desk, all of a sudden a fell."
    result = linkify_tickers(text, {"IT", "ALL", "ON", "A"})
    assert result == text


def test_uppercase_prose_word_matching_a_known_ticker_is_linked():
    # This is the accepted tradeoff named in research.md R5: case-sensitivity
    # is the safeguard, so a genuinely-uppercase mention of a ticker links,
    # even where (rarely) it might be emphasis rather than the symbol.
    result = linkify_tickers("Consider ON Semiconductor.", {"ON"})
    assert result == "Consider [ON](/stock/ON) Semiconductor."


def test_text_already_inside_a_markdown_link_is_not_rewritten():
    text = "See [NVDA overview](/stock/NVDA) for details."
    result = linkify_tickers(text, {"NVDA"})
    assert result == text


def test_ticker_inside_an_inline_code_span_is_not_rewritten():
    text = "The field is named `AAPL` internally."
    result = linkify_tickers(text, {"AAPL"})
    assert result == text


def test_ticker_inside_a_fenced_code_block_is_not_rewritten():
    text = "```\nticker = AAPL\n```"
    result = linkify_tickers(text, {"AAPL"})
    assert result == text


def test_empty_known_tickers_linkifies_nothing():
    text = "AAPL and NVDA both moved."
    result = linkify_tickers(text, set())
    assert result == text


def test_empty_text_returns_empty_text():
    assert linkify_tickers("", {"AAPL"}) == ""


def test_ticker_at_start_and_end_of_string_is_linked():
    result = linkify_tickers("AAPL", {"AAPL"})
    assert result == "[AAPL](/stock/AAPL)"


def test_ticker_followed_by_punctuation_is_linked_without_swallowing_it():
    result = linkify_tickers("Buy AAPL, sell NVDA.", {"AAPL", "NVDA"})
    assert result == "Buy [AAPL](/stock/AAPL), sell [NVDA](/stock/NVDA)."


def test_ticker_substring_inside_a_longer_word_is_not_linked():
    # "ON" must not match inside "CONSIDER" or "ONWARD" — word boundaries only.
    result = linkify_tickers("Consider the onward trend.", {"ON"})
    assert result == "Consider the onward trend."


def test_linkify_citation_returns_markdown_link():
    result = linkify_citation("Nvidia beats on datacenter revenue", "https://example.com/nvda")
    assert result == "[Nvidia beats on datacenter revenue](https://example.com/nvda)"

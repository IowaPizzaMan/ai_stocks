"""Unit tests for chunker/summarizer — LLM faked."""
import json

from chunker import chunker
from chunker.summarizer import summarize


def test_transcript_chunks_keep_speaker_turns_intact():
    segments = [{"name": f"Speaker{i}", "speech": "word " * 500} for i in range(6)]
    chunks = chunker.chunk(segments, "transcript", max_tokens=1000)
    assert len(chunks) > 1
    for c in chunks:
        # every chunk starts at a speaker boundary
        assert c.startswith("Speaker")
    # no speech got split across chunks: all six speakers appear exactly once
    joined = "\n".join(chunks)
    for i in range(6):
        assert joined.count(f"Speaker{i}:") == 1


def test_financials_chunked_by_statement():
    data = {"income_annual": [{"revenue": 1}], "balance_annual": [{"cash": 2}],
            "empty_section": []}
    chunks = chunker.chunk(data, "financials")
    assert len(chunks) == 2
    keys = {list(json.loads(c).keys())[0] for c in chunks}
    assert keys == {"income_annual", "balance_annual"}


def test_news_grouped_five_per_chunk():
    articles = [{"headline": f"h{i}"} for i in range(12)]
    chunks = chunker.chunk(articles, "news")
    assert len(chunks) == 3
    assert len(json.loads(chunks[0])) == 5
    assert len(json.loads(chunks[2])) == 2


def test_price_history_downsampled():
    data = {"daily": [{"c": i} for i in range(200)],
            "weekly": [{"c": i} for i in range(100)],
            "monthly": [{"c": i} for i in range(60)]}
    [chunk] = chunker.chunk(data, "price_history")
    parsed = json.loads(chunk)
    assert len(parsed["daily"]) == 60
    assert len(parsed["weekly"]) == 100
    assert len(parsed["monthly"]) == 24


def test_generic_split_by_size():
    chunks = chunker.chunk("x" * 20000, "other", max_tokens=1000)
    assert len(chunks) == 5
    assert all(len(c) <= 4000 for c in chunks)


class FakeClient:
    def __init__(self):
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs["messages"][-1]["content"])
        return {"message": {"content": f"summary-{len(self.calls)}"}}


def test_summarize_single_chunk_no_merge():
    client = FakeClient()
    out = summarize(["one chunk"], "news", "AAPL", client=client)
    assert out == "summary-1"
    assert len(client.calls) == 1
    assert "AAPL" in client.calls[0]


def test_summarize_multiple_chunks_merges():
    client = FakeClient()
    out = summarize(["a", "b", "c"], "transcript", "AAPL", client=client)
    # 3 chunk summaries + 1 merge call
    assert len(client.calls) == 4
    assert out == "summary-4"
    assert "Merge these transcript summaries" in client.calls[-1]


def test_summarize_empty_chunks():
    assert summarize(["", "  "], "news", "AAPL", client=FakeClient()) == ""

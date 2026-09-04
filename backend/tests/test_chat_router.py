"""Contract tests for the chat API.
Spec: specs/031-semantic-layer-chat; contracts/chat-api.md.

Ollama is faked via monkeypatching llm.get_client() — the same injection
seam agent-runner's agents use ("every agent takes client=None and forwards
it"). These tests validate the contract's shape and the fail-soft paths
(out-of-scope, rejected query) without depending on a live model; the actual
query-generation *quality* was verified manually against live Ollama +
real data during implementation (research.md R1/R4 reference values).
"""
import json
from datetime import datetime, timezone

import llm
from semantic import strategy_picks


class FakeOllamaClient:
    """format=<schema> calls return `query_response`; plain calls (the
    answer-interpretation step) return `answer_text`."""

    def __init__(self, query_response: dict, answer_text: str = "13 stocks matched: TPR, MO"):
        self.query_response = query_response
        self.answer_text = answer_text
        self.calls: list[dict] = []

    def chat(self, *, model, messages, format=None, think=None, keep_alive=None, options=None):
        self.calls.append({"messages": messages, "format": format})
        content = json.dumps(self.query_response) if format is not None else self.answer_text
        return {"message": {"content": content}}


class FailingOllamaClient:
    def chat(self, **kwargs):
        raise ConnectionError("ollama unreachable")


def screener_doc(ticker, **overrides):
    doc = {
        "ticker": ticker, "name": f"{ticker} Inc.", "sector": "Technology",
        "industry": "Software", "market_cap": 1_000_000_000.0, "is_tracked": True,
        "last_close": 100.0, "last_bar_date": "2026-08-21",
        "range_pct_20d": 0.1, "zscore_20d": -0.5, "weekly_change_pct": 1.0,
        "monthly_change_pct": 2.0, "weekly_trend": "up",
        "revenue_growth_yoy": 0.1, "net_income_growth_yoy": 0.08,
        "net_profit_margin": 0.2, "margin_trend": "improving",
        "financials_trend": "improving", "free_cash_flow": 1000.0,
        "total_debt": 500.0, "fcf_exceeds_debt": True,
        "signals_as_of": datetime.now(timezone.utc), "price_data_through": "2026-08-21",
        "financials_as_of": "2025-12-31", "insufficient_history": False,
    }
    doc.update(overrides)
    return doc


def test_flagship_question_returns_grounded_answer(client, db, monkeypatch):
    db["screener"].insert_many([
        screener_doc("TPR"), screener_doc("MO"),
        screener_doc("AAPL", zscore_20d=0.5, fcf_exceeds_debt=False),  # doesn't match
    ])
    fake = FakeOllamaClient({
        "collection": "screener",
        "pipeline": [{"$match": {"zscore_20d": {"$lt": 0}, "financials_trend": "improving",
                                  "fcf_exceeds_debt": True}}],
        "in_scope": True,
    })
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    resp = client.post("/chat", json={
        "question": "what stocks are at the bottom of their daily z-score range but "
                    "moving up on the weekly, with improving financials and more free "
                    "cash flow than debt?",
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["match_count"] == 2
    assert {r["ticker"] for r in body["rows"]} == {"TPR", "MO"}
    assert body["answer"]
    assert len(body["criteria"]) == 3
    assert body["generated_query"]["collection"] == "screener"
    assert body["degraded"] is False
    assert body["note"] is None


def test_out_of_scope_question_declines_without_fabricating(client, db, monkeypatch):
    db["screener"].insert_one(screener_doc("AAPL"))
    fake = FakeOllamaClient({"collection": "screener", "pipeline": [], "in_scope": False})
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    resp = client.post("/chat", json={"question": "what is the CEO's favorite color?"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["note"] == "out_of_scope"
    assert body["generated_query"] is None
    assert body["match_count"] == 0
    assert body["answer"]


def test_aggregation_question_returns_grouped_rows(client, db, monkeypatch):
    """specs/035-chat-and-news-upgrade US1 (FR-010, FR-011) — a question
    shaped as an aggregation must actually produce a $group pipeline and
    grouped (not per-ticker) rows, not just a filtered list."""
    db["screener"].insert_many([
        screener_doc("TPR", sector="Technology", weekly_change_pct=2.0),
        screener_doc("MO", sector="Technology", weekly_change_pct=4.0),
        screener_doc("AAPL", sector="Consumer Electronics", weekly_change_pct=1.0),
    ])
    fake = FakeOllamaClient({
        "collection": "screener",
        "pipeline": [
            {"$group": {"_id": "$sector", "avg_change": {"$avg": "$weekly_change_pct"}}},
        ],
        "in_scope": True,
    }, answer_text="Technology averaged +3% this week.")
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    resp = client.post("/chat", json={"question": "what's the average weekly change by sector?"})

    assert resp.status_code == 200
    body = resp.json()
    assert any("$group" in stage for stage in body["generated_query"]["pipeline"])
    assert {"_id", "avg_change"}.issubset(body["rows"][0].keys())


def news_doc(url, **overrides):
    doc = {
        "url": url, "source_type": "stock", "title": f"headline for {url}",
        "published_at": datetime.now(timezone.utc), "published_date": "2026-08-25",
        "publisher": "CNBC", "site": "cnbc.com", "author": None,
        "body_html": None, "body_text": "body", "image_url": None,
        "tickers": ["NVDA"], "ingested_at": datetime.now(timezone.utc),
    }
    doc.update(overrides)
    return doc


def test_news_question_executes_against_news_articles_not_screener(client, db, monkeypatch):
    """specs/035-chat-and-news-upgrade US3 — regression test for research.md
    R2: chat.py validated a `collection` variable but then hardcoded
    db[SCREENER] when executing. Seeding both collections with an NVDA
    document under the SAME ticker proves the response's rows actually came
    from the collection the model chose, not always screener."""
    db["news_articles"].insert_one(news_doc("https://x/nvda", title="Nvidia beats on datacenter revenue"))
    db["screener"].insert_one(screener_doc("NVDA"))  # decoy — must NOT be what's returned

    fake = FakeOllamaClient({
        "collection": "news_articles",
        "pipeline": [{"$match": {"tickers": "NVDA"}}],
        "in_scope": True,
    }, answer_text="Nvidia beat on datacenter revenue, per a recent CNBC story.")
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    resp = client.post("/chat", json={"question": "what's the latest news on NVDA?"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["generated_query"]["collection"] == "news_articles"
    assert body["rows"]
    assert "title" in body["rows"][0] and "url" in body["rows"][0]
    assert "sector" not in body["rows"][0]  # would only appear if screener was queried instead
    assert body["citations"]
    assert body["citations"][0]["title"] == "Nvidia beats on datacenter revenue"
    assert body["citations"][0]["url"] == "https://x/nvda"
    # FR-008 — the citation must be a clickable link in the answer itself,
    # not just structured metadata on the side (research.md R5's
    # linkify_citation, same mechanism FR-013 uses for tickers).
    assert "[Nvidia beats on datacenter revenue](https://x/nvda)" in body["answer"]


def test_news_question_with_no_matches_returns_empty_citations(client, db, monkeypatch):
    db["news_articles"].insert_one(news_doc("https://x/other", tickers=["AAPL"]))
    fake = FakeOllamaClient({
        "collection": "news_articles",
        "pipeline": [{"$match": {"tickers": "ZZZZNOTAREALTICKER"}}],
        "in_scope": True,
    }, answer_text="I couldn't find any recent news about that.")
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    resp = client.post("/chat", json={"question": "what's the latest news on ZZZZNOTAREALTICKER?"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["rows"] == []
    assert body["citations"] == []


def test_answer_linkifies_a_tracked_ticker_mentioned_in_the_prose(client, db, monkeypatch):
    """specs/035-chat-and-news-upgrade US4 (FR-013)."""
    db["screener"].insert_many([screener_doc("TPR"), screener_doc("MO")])
    fake = FakeOllamaClient({
        "collection": "screener",
        "pipeline": [{"$match": {}}],
        "in_scope": True,
    }, answer_text="TPR and MO both look strong this week.")
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    resp = client.post("/chat", json={"question": "what stocks look strong?"})

    body = resp.json()
    assert "[TPR](/stock/TPR)" in body["answer"]
    assert "[MO](/stock/MO)" in body["answer"]


def test_answer_does_not_linkify_a_word_that_is_not_a_tracked_ticker(client, db, monkeypatch):
    """specs/035-chat-and-news-upgrade US4 (FR-014) — a ticker-shaped word
    that isn't actually a tracked stock must never become a link."""
    db["screener"].insert_one(screener_doc("TPR"))
    fake = FakeOllamaClient({
        "collection": "screener",
        "pipeline": [{"$match": {}}],
        "in_scope": True,
    }, answer_text="TPR is the only one that qualifies, unlike ZZZZ which isn't tracked.")
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    resp = client.post("/chat", json={"question": "what stocks look strong?"})

    body = resp.json()
    assert "[TPR](/stock/TPR)" in body["answer"]
    assert "[ZZZZ]" not in body["answer"]
    assert "ZZZZ" in body["answer"]


def _screener_fake(answer_text="ok"):
    return FakeOllamaClient({"collection": "screener", "pipeline": [{"$match": {}}], "in_scope": True},
                             answer_text=answer_text)


def test_post_chat_without_conversation_id_creates_one(client, db, monkeypatch):
    """specs/035-chat-and-news-upgrade US5 (FR-015, FR-016)."""
    db["screener"].insert_one(screener_doc("TPR"))
    monkeypatch.setattr(llm, "get_client", lambda: _screener_fake())
    from semantic import chat as chat_module
    monkeypatch.setattr(
        chat_module.conversations, "_generate_title",
        lambda question, answer, *, client=None: "TPR Overview",
    )

    resp = client.post("/chat", json={"question": "how's TPR doing?"})

    body = resp.json()
    assert body["conversation_id"] is not None
    assert body["conversation_title"] == "TPR Overview"
    stored = db["chat_conversations"].find_one({})
    assert stored is not None
    assert stored["title"] == "TPR Overview"


def test_post_chat_with_conversation_id_appends_and_omits_title(client, db, monkeypatch):
    db["screener"].insert_one(screener_doc("TPR"))
    monkeypatch.setattr(llm, "get_client", lambda: _screener_fake())
    from semantic import chat as chat_module
    monkeypatch.setattr(
        chat_module.conversations, "_generate_title",
        lambda question, answer, *, client=None: "TPR Overview",
    )

    first = client.post("/chat", json={"question": "how's TPR doing?"}).json()
    conversation_id = first["conversation_id"]

    second = client.post(
        "/chat", json={"question": "and now?", "conversation_id": conversation_id},
    ).json()

    assert second["conversation_id"] == conversation_id
    assert second["conversation_title"] is None
    stored = db["chat_conversations"].find_one({})
    assert len(stored["messages"]) == 4


def test_post_chat_with_unknown_conversation_id_is_404(client, db, monkeypatch):
    db["screener"].insert_one(screener_doc("TPR"))
    monkeypatch.setattr(llm, "get_client", lambda: _screener_fake())

    resp = client.post(
        "/chat", json={"question": "anything", "conversation_id": "000000000000000000000000"},
    )
    assert resp.status_code == 404


def test_conversation_persistence_failure_still_returns_the_answer(client, db, monkeypatch):
    """A history-write failure must never cost the user the answer they waited for."""
    db["screener"].insert_one(screener_doc("TPR"))
    monkeypatch.setattr(llm, "get_client", lambda: _screener_fake("TPR looks fine."))
    from semantic import chat as chat_module

    def boom(*args, **kwargs):
        raise RuntimeError("mongo write failed")

    monkeypatch.setattr(chat_module.conversations, "create", boom)

    resp = client.post("/chat", json={"question": "how's TPR doing?"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"]
    assert body["conversation_id"] is None
    assert body["conversation_title"] is None


def test_disallowed_generated_query_is_rejected_not_500(client, db, monkeypatch):
    db["screener"].insert_one(screener_doc("AAPL"))
    fake = FakeOllamaClient({
        "collection": "screener",
        "pipeline": [{"$out": "some_other_collection"}],
        "in_scope": True,
    })
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    resp = client.post("/chat", json={"question": "delete everything"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["note"] == "query_rejected"
    assert body["match_count"] == 0
    # the DB must be untouched — this is the actual FR-012/SC-007 assurance
    assert db["screener"].count_documents({}) == 1


def test_empty_screener_degrades_gracefully(client, db, monkeypatch):
    """033-strategy-picks-filters FR-001: detect() now runs unconditionally
    before the emptiness check (a strategy-picks question reads
    strategy_signals, not screener, so it can't be gated on screener data).

    specs/035-chat-and-news-upgrade US3 (research.md R2) moved the
    emptiness gate to AFTER the collection is known — an empty screener
    must not block a question that actually targets news_articles. So the
    gate now runs after generate_pipeline(), not before it: both detect()
    and generate_pipeline() are called (2), and only then — once the chosen
    collection (screener, since this fake response has no "collection" key)
    is found empty — does it degrade rather than execute an aggregate."""
    fake = FakeOllamaClient({
        "is_strategy_picks": False, "direction": None, "count": None,
        "named_strategy": None, "unrecognized_strategy_text": None, "extra_conditions": None,
    })
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    resp = client.post("/chat", json={"question": "anything"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["degraded"] is True
    assert body["note"] == "no_data"
    assert len(fake.calls) == 2


def test_ollama_unreachable_degrades_to_200_not_503(client, db, monkeypatch):
    db["screener"].insert_one(screener_doc("AAPL"))
    monkeypatch.setattr(llm, "get_client", lambda: FailingOllamaClient())

    resp = client.post("/chat", json={"question": "anything"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["degraded"] is True
    assert body["note"] == "model_unavailable"


def test_empty_question_is_422(client, db):
    resp = client.post("/chat", json={"question": "   "})
    assert resp.status_code == 422


def test_oversized_question_is_422(client, db):
    resp = client.post("/chat", json={"question": "x" * 2001})
    assert resp.status_code == 422


def test_follow_up_question_receives_replayed_history(client, db, monkeypatch):
    """FR-003/US2: history is replayed to the model on each turn; nothing is
    stored server-side (FR-004) — the request itself carries all context."""
    db["screener"].insert_many([screener_doc("TPR"), screener_doc("MO")])
    fake = FakeOllamaClient({
        "collection": "screener",
        "pipeline": [{"$match": {"ticker": {"$in": ["TPR", "MO"]}}}, {"$sort": {"market_cap": -1}}],
        "in_scope": True,
    }, answer_text="TPR has the higher market cap.")
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    resp = client.post("/chat", json={
        "question": "which of those has the highest market cap?",
        "history": [
            {"role": "user", "content": "what stocks are near their 20-day low?"},
            {"role": "assistant", "content": "13 stocks matched: TPR, MO, AAPL"},
        ],
    })

    assert resp.status_code == 200
    # the history must actually reach the query-generation prompt
    query_gen_call = next(c for c in fake.calls if c["format"] is not None)
    prompt_text = query_gen_call["messages"][-1]["content"]
    assert "TPR, MO, AAPL" in prompt_text
    assert "which of those has the highest market cap?" in prompt_text


def test_history_is_truncated_to_the_most_recent_turns(client, db, monkeypatch):
    """research.md R9 — an unbounded replay would grow the prompt until
    latency regresses past SC-001; server-side truncation caps it regardless
    of what the client sends."""
    db["screener"].insert_one(screener_doc("AAPL"))
    fake = FakeOllamaClient({"collection": "screener", "pipeline": [{"$match": {}}], "in_scope": True})
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    long_history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"turn-{i}"}
        for i in range(20)
    ]
    resp = client.post("/chat", json={"question": "final question", "history": long_history})

    assert resp.status_code == 200
    query_gen_call = next(c for c in fake.calls if c["format"] is not None)
    prompt_text = query_gen_call["messages"][-1]["content"]
    assert "turn-19" in prompt_text  # most recent turn kept
    assert "turn-0" not in prompt_text  # oldest turns dropped


def test_ordinary_screener_question_is_unaffected_by_strategy_picks_dispatch(client, db, monkeypatch):
    """032-weekly-strategy-picks FR-011 regression, updated for
    033-strategy-picks-filters FR-001: an ordinary screener question must
    still return strategy_picks: null with rows/criteria/generated_query
    populated exactly as before this feature — even though detect() is now
    called unconditionally (the keyword pre-filter is gone) and says no."""
    db["screener"].insert_many([screener_doc("TPR"), screener_doc("MO")])

    calls = {"n": 0}

    class RoutingFakeClient:
        def chat(self, *, model, messages, format=None, think=None, keep_alive=None, options=None):
            calls["n"] += 1
            if calls["n"] == 1:
                return {"message": {"content": json.dumps({
                    "is_strategy_picks": False, "direction": None, "count": None,
                    "named_strategy": None, "unrecognized_strategy_text": None,
                    "extra_conditions": None,
                })}}
            if format is not None:
                return {"message": {"content": json.dumps({
                    "collection": "screener",
                    "pipeline": [{"$match": {"zscore_20d": {"$lt": 0}}}], "in_scope": True,
                })}}
            return {"message": {"content": "2 stocks matched: TPR, MO"}}

    monkeypatch.setattr(llm, "get_client", lambda: RoutingFakeClient())

    resp = client.post("/chat", json={
        "question": "what stocks are near the bottom of their 20-day range?",
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["strategy_picks"] is None
    assert body["generated_query"]["collection"] == "screener"
    assert body["match_count"] == 2
    # detect() + query-generation + answer-interpretation + conversation-title
    # generation (specs/035-chat-and-news-upgrade US5 — a successful,
    # non-degraded exchange is always persisted) — one detect() call now
    # always precedes the free-form flow (FR-001)
    assert calls["n"] == 4


def test_strategy_keyword_present_but_not_a_picks_question_falls_through(client, db, monkeypatch):
    """033-strategy-picks-filters FR-001: detect() runs on every question and
    can still say no even when the question happens to mention "strategy" —
    that must fall through to the existing free-form flow rather than
    forcing a strategy_picks answer."""
    db["screener"].insert_many([screener_doc("TPR")])

    calls = {"n": 0}

    class RoutingFakeClient:
        def chat(self, *, model, messages, format=None, think=None, keep_alive=None, options=None):
            calls["n"] += 1
            if calls["n"] == 1:
                # first call: strategy_picks.detect() — says no
                return {"message": {"content": json.dumps({
                    "is_strategy_picks": False, "direction": None, "count": None,
                    "named_strategy": None, "unrecognized_strategy_text": None,
                    "extra_conditions": None,
                })}}
            if format is not None:
                # second call: the existing free-form query generator
                return {"message": {"content": json.dumps({
                    "collection": "screener", "pipeline": [{"$match": {}}], "in_scope": True,
                })}}
            return {"message": {"content": "1 stock matched: TPR"}}

    monkeypatch.setattr(llm, "get_client", lambda: RoutingFakeClient())

    resp = client.post("/chat", json={
        "question": "what's a good strategy for finding value stocks in general?",
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["strategy_picks"] is None
    assert body["generated_query"] is not None


class MultiCallFakeClient:
    """033-strategy-picks-filters: a combined-condition question makes three
    schema/plain calls in order — detect() (schema), condition_filter's
    translate_conditions() (schema), narrate() (plain)."""

    def __init__(self, schema_responses: list[dict], answer_text: str = "Here are your picks."):
        self.schema_responses = list(schema_responses)
        self.answer_text = answer_text
        self.calls: list[dict] = []

    def chat(self, *, model, messages, format=None, think=None, keep_alive=None, options=None):
        self.calls.append({"messages": messages, "format": format})
        if format is not None:
            response = self.schema_responses.pop(0)
            return {"message": {"content": json.dumps(response)}}
        return {"message": {"content": self.answer_text}}


def test_strategy_picks_with_combined_condition_narrows_and_reports_criteria(client, db, monkeypatch):
    """033-strategy-picks-filters US1/contract: a strategy-picks question
    naming liked+sector conditions returns strategy_picks.condition_requested/
    condition_applied/condition_note plus the top-level criteria field
    populated, per contracts/strategy-picks-filters-api.md."""
    from db import STRATEGY_SIGNALS

    db[STRATEGY_SIGNALS].insert_many([
        {"ticker": "KO", "the_strat": {"direction": "long", "pattern": "revstrat_2bar_bullish",
                                        "timeframe": "weekly", "entry_price": 61.2, "strength": 3},
         "gap_analysis": {"direction": None, "score": None, "entry_price": None, "bias": None}},
    ])
    db["screener"].insert_one({"ticker": "KO", "liked_status": "liked", "sector": "Consumer Staples"})
    fake = MultiCallFakeClient([
        {"is_strategy_picks": True, "direction": "buy", "count": None,
         "named_strategy": None, "unrecognized_strategy_text": None,
         "extra_conditions": ["only stocks I've liked", "in the consumer staples sector"]},
        {"collection": "screener",
         "pipeline": [{"$match": {"liked_status": "liked", "sector": "Consumer Staples"}}],
         "in_scope": True},
    ], answer_text=f"KO at 61.2. {strategy_picks.DISCLAIMER}")
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    resp = client.post("/chat", json={
        "question": "per my strategies, give me liked stocks in the consumer staples sector to buy this week",
    })

    assert resp.status_code == 200
    body = resp.json()
    picks = body["strategy_picks"]
    assert picks is not None
    assert picks["condition_requested"] == "only stocks I've liked; in the consumer staples sector"
    assert picks["condition_applied"] is True
    assert picks["condition_note"] is None
    assert len(body["criteria"]) == 2
    the_strat = next(e for e in picks["lists"] if e["strategy"] == "the_strat")
    assert [c["ticker"] for c in the_strat["candidates"]] == ["KO"]


def test_unanswerable_condition_still_returns_unfiltered_strategy_picks(client, db, monkeypatch):
    """033-strategy-picks-filters US3/FR-007, contract's "condition couldn't
    be applied" example: the strategy-picks answer is still returned, full
    and unfiltered, alongside an explanatory condition_note — not a failed
    request."""
    from db import STRATEGY_SIGNALS

    db[STRATEGY_SIGNALS].insert_one({
        "ticker": "KO", "the_strat": {"direction": "long", "pattern": "revstrat_2bar_bullish",
                                       "timeframe": "weekly", "entry_price": 61.2, "strength": 3},
        "gap_analysis": {"direction": None, "score": None, "entry_price": None, "bias": None},
    })
    fake = MultiCallFakeClient([
        {"is_strategy_picks": True, "direction": "buy", "count": None,
         "named_strategy": None, "unrecognized_strategy_text": None,
         "extra_conditions": ["most popular in consumer staples"]},
        {"collection": "screener", "pipeline": [], "in_scope": False},
    ], answer_text=f"KO at 61.2. {strategy_picks.DISCLAIMER}")
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    resp = client.post("/chat", json={
        "question": "what are the most popular stocks in consumer staples ready to buy per my strategy",
    })

    assert resp.status_code == 200
    body = resp.json()
    picks = body["strategy_picks"]
    assert picks is not None
    assert picks["condition_requested"] == "most popular in consumer staples"
    assert picks["condition_applied"] is False
    assert picks["condition_note"] is not None
    assert body["criteria"] == []
    the_strat = next(e for e in picks["lists"] if e["strategy"] == "the_strat")
    assert [c["ticker"] for c in the_strat["candidates"]] == ["KO"]


def test_detect_is_invoked_unconditionally_even_without_a_keyword(client, db, monkeypatch):
    """033-strategy-picks-filters US2/FR-001: the keyword pre-filter is gone
    — answer_question() must call strategy_picks.detect() on every question,
    even one with none of the old trigger keywords in it."""
    db["screener"].insert_one(screener_doc("AAPL"))
    calls = {"detect": 0}
    original_detect = strategy_picks.detect

    def spy_detect(question, history, *, client=None):
        calls["detect"] += 1
        return original_detect(question, history, client=client)

    monkeypatch.setattr(strategy_picks, "detect", spy_detect)

    fake = FakeOllamaClient({"collection": "screener", "pipeline": [{"$match": {}}], "in_scope": True})
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    resp = client.post("/chat", json={
        "question": "what stocks have improving financials and free cash flow exceeding debt?",
    })

    assert resp.status_code == 200
    assert calls["detect"] == 1


def test_chat_schema_endpoint_reports_document_count(client, db):
    db["screener"].insert_many([screener_doc("AAPL"), screener_doc("MSFT")])
    resp = client.get("/chat/schema")
    assert resp.status_code == 200
    body = resp.json()
    assert body["collection"] == "screener"
    assert body["document_count"] == 2
    assert any(f["name"] == "fcf_exceeds_debt" for f in body["fields"])

"""Strategy picks: intent detection -> deterministic ranking -> Market Flow
filter -> narration. Spec: specs/032-weekly-strategy-picks;
contracts/strategy-picks-api.md.
"""
import json

from db import BREADTH_CACHE, SCREENER, STRATEGY_SIGNALS
from semantic import strategy_picks


class FakeOllamaClient:
    """format=<schema> calls (detect()) return `intent_response`; plain calls
    (narrate()) return `answer_text`. Mirrors test_chat_router.py's fake."""

    def __init__(self, intent_response: dict, answer_text: str = "Here are your picks."):
        self.intent_response = intent_response
        self.answer_text = answer_text
        self.calls: list[dict] = []

    def chat(self, *, model, messages, format=None, think=None, keep_alive=None, options=None):
        self.calls.append({"messages": messages, "format": format})
        content = json.dumps(self.intent_response) if format is not None else self.answer_text
        return {"message": {"content": content}}


class FailingOllamaClient:
    def chat(self, **kwargs):
        raise ConnectionError("ollama unreachable")


class MultiCallFakeClient:
    """033-strategy-picks-filters: a combined-condition question makes three
    calls in order — detect() (schema), condition_filter.translate_conditions()
    (schema, only when extra_conditions is non-empty), narrate() (plain).
    `schema_responses` supplies the schema-call return values in call order."""

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


def strat_doc(ticker, direction="long", strength=2, entry_price=100.0,
              pattern="revstrat_2bar_bullish", timeframe="weekly"):
    return {"ticker": ticker, "direction": direction, "strength": strength,
            "entry_price": entry_price, "pattern": pattern, "timeframe": timeframe}


def gap_doc(ticker, direction="long", score=4, entry_price=100.0, bias="LONG at day 3+"):
    return {"ticker": ticker, "direction": direction, "score": score,
            "entry_price": entry_price, "bias": bias}


def signals_doc(ticker, the_strat=None, gap_analysis=None):
    null_strat = {"direction": None, "pattern": None, "timeframe": None,
                  "entry_price": None, "strength": 0}
    null_gap = {"direction": None, "score": None, "entry_price": None, "bias": None}
    return {
        "ticker": ticker,
        "the_strat": the_strat or null_strat,
        "gap_analysis": gap_analysis or null_gap,
    }


# --- _resolve_count (FR-016) ------------------------------------------------

def test_resolve_count_uses_default_when_none():
    assert strategy_picks._resolve_count(None) == strategy_picks.DEFAULT_COUNT


def test_resolve_count_honors_a_valid_request():
    assert strategy_picks._resolve_count(5) == 5


def test_resolve_count_falls_back_on_zero_or_negative():
    assert strategy_picks._resolve_count(0) == strategy_picks.DEFAULT_COUNT
    assert strategy_picks._resolve_count(-3) == strategy_picks.DEFAULT_COUNT


def test_resolve_count_falls_back_on_unreasonably_large():
    assert strategy_picks._resolve_count(500) == strategy_picks.DEFAULT_COUNT


def test_resolve_count_falls_back_on_non_integer():
    assert strategy_picks._resolve_count("five") == strategy_picks.DEFAULT_COUNT
    assert strategy_picks._resolve_count(True) == strategy_picks.DEFAULT_COUNT


# --- compute_picks: ranking, entry prices, no padding, ties -----------------

def test_compute_picks_ranks_by_strength_and_ties_break_by_ticker(db):
    db[STRATEGY_SIGNALS].insert_many([
        signals_doc("ZZZZ", the_strat=strat_doc("ZZZZ", strength=3)),
        signals_doc("AAAA", the_strat=strat_doc("AAAA", strength=3)),  # tie on strength -> ticker asc
        signals_doc("BBBB", the_strat=strat_doc("BBBB", strength=1)),
    ])
    picks = strategy_picks.compute_picks("buy", 10, db)
    the_strat = next(entry for entry in picks["lists"] if entry["strategy"] == "the_strat")
    tickers = [c["ticker"] for c in the_strat["candidates"]]
    assert tickers == ["AAAA", "ZZZZ", "BBBB"]


def test_compute_picks_every_candidate_has_a_specific_entry_price(db):
    db[STRATEGY_SIGNALS].insert_one(signals_doc(
        "AAPL", the_strat=strat_doc("AAPL", entry_price=187.5),
        gap_analysis=gap_doc("AAPL", entry_price=182.1),
    ))
    picks = strategy_picks.compute_picks("buy", 10, db)
    for entry in picks["lists"]:
        for c in entry["candidates"]:
            assert isinstance(c["entry_price"], (int, float))


def test_compute_picks_does_not_pad_short_lists(db):
    db[STRATEGY_SIGNALS].insert_many([signals_doc(f"T{i}", the_strat=strat_doc(f"T{i}")) for i in range(3)])
    picks = strategy_picks.compute_picks("buy", 10, db)
    the_strat = next(entry for entry in picks["lists"] if entry["strategy"] == "the_strat")
    assert len(the_strat["candidates"]) == 3  # not padded to 10


def test_compute_picks_zero_candidates_states_so_via_note(db):
    picks = strategy_picks.compute_picks("buy", 10, db)  # empty collection
    for entry in picks["lists"]:
        assert entry["candidates"] == []
        assert entry["note"] == "no candidates currently qualify this week"


def test_compute_picks_short_direction_uses_short_field(db):
    db[STRATEGY_SIGNALS].insert_one(signals_doc(
        "XOM", the_strat=strat_doc("XOM", direction="short", entry_price=95.0, pattern="shooting_star"),
    ))
    picks = strategy_picks.compute_picks("short", 10, db)
    the_strat = next(entry for entry in picks["lists"] if entry["strategy"] == "the_strat")
    assert [c["ticker"] for c in the_strat["candidates"]] == ["XOM"]


# --- US2: short direction, full parity with the buy-direction coverage above ---

def test_compute_picks_short_direction_full_lists_both_strategies(db):
    db[STRATEGY_SIGNALS].insert_many([
        signals_doc("XOM", the_strat=strat_doc("XOM", direction="short", entry_price=95.0,
                                                pattern="shooting_star")),
        signals_doc("CVX", gap_analysis=gap_doc("CVX", direction="short", entry_price=150.0,
                                                 bias="SHORT days 1-10, LONG by day 30")),
    ])
    picks = strategy_picks.compute_picks("short", 10, db)
    assert picks["direction"] == "short"
    the_strat = next(e for e in picks["lists"] if e["strategy"] == "the_strat")
    gap = next(e for e in picks["lists"] if e["strategy"] == "gap_analysis")
    assert [c["ticker"] for c in the_strat["candidates"]] == ["XOM"]
    assert [c["ticker"] for c in gap["candidates"]] == ["CVX"]
    for entry in picks["lists"]:
        for c in entry["candidates"]:
            assert isinstance(c["entry_price"], (int, float))


def test_compute_picks_short_direction_does_not_pad_or_leak_long_candidates(db):
    # AAPL only qualifies long — must not appear in a short-direction list
    db[STRATEGY_SIGNALS].insert_many([
        signals_doc("AAPL", the_strat=strat_doc("AAPL", direction="long")),
        signals_doc("XOM", the_strat=strat_doc("XOM", direction="short")),
    ])
    picks = strategy_picks.compute_picks("short", 10, db)
    the_strat = next(e for e in picks["lists"] if e["strategy"] == "the_strat")
    assert [c["ticker"] for c in the_strat["candidates"]] == ["XOM"]


def test_compute_picks_short_direction_zero_candidates_states_so_via_note(db):
    """FR-003 edge case: a strategy with no qualifying short-side signal for
    the week states so plainly, same as the buy-direction FR-007 case."""
    db[STRATEGY_SIGNALS].insert_one(signals_doc("AAPL", the_strat=strat_doc("AAPL", direction="long")))
    picks = strategy_picks.compute_picks("short", 10, db)
    for entry in picks["lists"]:
        assert entry["candidates"] == []
        assert entry["note"] == "no candidates currently qualify this week"


def test_compute_picks_oversold_excludes_all_short_candidates(db):
    """FR-017 mirrored for shorts: an oversold NYMO reading excludes an
    otherwise-qualifying short candidate, with the correct reason text."""
    db[STRATEGY_SIGNALS].insert_one(signals_doc(
        "XOM", the_strat=strat_doc("XOM", direction="short", entry_price=95.0),
    ))
    db[BREADTH_CACHE].insert_one({"exchange": "nyse", "date": "2026-08-23", "mcclellan": -72.0})

    picks = strategy_picks.compute_picks("short", 10, db)

    the_strat = next(e for e in picks["lists"] if e["strategy"] == "the_strat")
    assert the_strat["candidates"] == []
    assert "oversold" in the_strat["note"]
    assert picks["excluded_by_market_flow"][0]["ticker"] == "XOM"
    assert "oversold" in picks["market_condition_note"]


def test_answer_strategy_picks_short_direction_round_trip(db):
    db[STRATEGY_SIGNALS].insert_one(signals_doc(
        "XOM", the_strat=strat_doc("XOM", direction="short", entry_price=95.0, pattern="shooting_star"),
    ))
    fake = FakeOllamaClient(
        {"is_strategy_picks": True, "direction": "short", "count": None,
         "named_strategy": None, "unrecognized_strategy_text": None},
        answer_text=f"XOM short at 95.0. {strategy_picks.DISCLAIMER}",
    )
    result = strategy_picks.answer_strategy_picks(
        "per my trading strategies what should I short this week", [], db, client=fake,
    )
    assert result["strategy_picks"]["direction"] == "short"
    assert strategy_picks.DISCLAIMER in result["answer"]
    assert result["match_count"] == 1


def test_compute_picks_respects_requested_count(db):
    db[STRATEGY_SIGNALS].insert_many([signals_doc(f"T{i}", the_strat=strat_doc(f"T{i}")) for i in range(8)])
    picks = strategy_picks.compute_picks("buy", 5, db)
    the_strat = next(entry for entry in picks["lists"] if entry["strategy"] == "the_strat")
    assert len(the_strat["candidates"]) == 5


# --- compute_picks: FR-015 partial-strategy failure --------------------------

def test_compute_picks_one_strategy_failing_does_not_sink_the_other(db, monkeypatch):
    db[STRATEGY_SIGNALS].insert_one(signals_doc("AAPL", the_strat=strat_doc("AAPL")))
    original_rank = strategy_picks._rank_strategy

    def flaky(strategy, field_direction, count, db, ticker_filter=None):
        if strategy == "gap_analysis":
            raise RuntimeError("boom")
        return original_rank(strategy, field_direction, count, db, ticker_filter)

    monkeypatch.setattr(strategy_picks, "_rank_strategy", flaky)

    picks = strategy_picks.compute_picks("buy", 10, db)
    the_strat = next(e for e in picks["lists"] if e["strategy"] == "the_strat")
    gap = next(e for e in picks["lists"] if e["strategy"] == "gap_analysis")
    assert [c["ticker"] for c in the_strat["candidates"]] == ["AAPL"]
    assert gap["candidates"] == []
    assert gap["note"] == "temporarily unavailable"


# --- compute_picks: Market Flow integration (FR-017) --------------------------

def test_compute_picks_overbought_excludes_all_buy_candidates(db):
    db[STRATEGY_SIGNALS].insert_many([
        signals_doc("AAPL", the_strat=strat_doc("AAPL")),
        signals_doc("MSFT", gap_analysis=gap_doc("MSFT")),
    ])
    db[BREADTH_CACHE].insert_one({"exchange": "nyse", "date": "2026-08-23", "mcclellan": 68.0})

    picks = strategy_picks.compute_picks("buy", 10, db)

    for entry in picks["lists"]:
        assert entry["candidates"] == []
        assert "overbought" in entry["note"]
    assert {item["ticker"] for item in picks["excluded_by_market_flow"]} == {"AAPL", "MSFT"}
    assert picks["market_condition_note"] is not None and "overbought" in picks["market_condition_note"]
    assert picks["market_condition_unavailable"] is False


def test_compute_picks_missing_breadth_data_still_returns_lists(db):
    db[STRATEGY_SIGNALS].insert_one(signals_doc("AAPL", the_strat=strat_doc("AAPL")))
    picks = strategy_picks.compute_picks("buy", 10, db)
    assert picks["market_condition_unavailable"] is True
    the_strat = next(e for e in picks["lists"] if e["strategy"] == "the_strat")
    assert [c["ticker"] for c in the_strat["candidates"]] == ["AAPL"]


# --- compute_picks: ticker_filter narrowing (033-strategy-picks-filters US1) --

def test_compute_picks_ticker_filter_excludes_non_matching_before_ranking(db):
    """FR-003: a filtered-out stock must never occupy a slot a qualifying
    stock should get — the filter narrows the Mongo predicate, not a
    post-hoc Python trim of an already-limited list."""
    db[STRATEGY_SIGNALS].insert_many([
        signals_doc("ZZZZ", the_strat=strat_doc("ZZZZ", strength=4)),  # excluded by filter
        signals_doc("AAAA", the_strat=strat_doc("AAAA", strength=1)),  # included, lower strength
    ])
    picks = strategy_picks.compute_picks("buy", 10, db, ticker_filter={"AAAA"})
    the_strat = next(e for e in picks["lists"] if e["strategy"] == "the_strat")
    assert [c["ticker"] for c in the_strat["candidates"]] == ["AAAA"]


def test_compute_picks_ticker_filter_respects_count_limit_after_narrowing(db):
    """A narrowing ticker_filter combined with a small requested count must
    still rank/limit only within the filtered set — never pad with an
    excluded ticker to reach count."""
    db[STRATEGY_SIGNALS].insert_many([
        signals_doc("AAAA", the_strat=strat_doc("AAAA", strength=3)),
        signals_doc("BBBB", the_strat=strat_doc("BBBB", strength=2)),
        signals_doc("CCCC", the_strat=strat_doc("CCCC", strength=1)),  # excluded by filter
    ])
    picks = strategy_picks.compute_picks("buy", 1, db, ticker_filter={"AAAA", "BBBB"})
    the_strat = next(e for e in picks["lists"] if e["strategy"] == "the_strat")
    assert [c["ticker"] for c in the_strat["candidates"]] == ["AAAA"]


def test_compute_picks_empty_ticker_filter_is_a_legitimate_zero_match(db):
    """FR-006: an empty (but non-None) ticker_filter is a real zero-match
    result, not an error — every list is empty with a note naming the
    condition."""
    db[STRATEGY_SIGNALS].insert_one(signals_doc("AAPL", the_strat=strat_doc("AAPL")))
    picks = strategy_picks.compute_picks(
        "buy", 10, db, ticker_filter=set(), condition_label="liked stocks in consumer staples",
    )
    for entry in picks["lists"]:
        assert entry["candidates"] == []
        assert entry["note"] == "no candidates currently qualify under liked stocks in consumer staples this week"


def test_compute_picks_no_ticker_filter_uses_generic_empty_note(db):
    """Regression: a plain strategy-picks question (no condition) must keep
    032's exact empty-note wording."""
    picks = strategy_picks.compute_picks("buy", 10, db)
    for entry in picks["lists"]:
        assert entry["note"] == "no candidates currently qualify this week"


# --- detect(): intent parsing (schema shape, history passed through) --------

def test_detect_parses_direction_count_and_strategy():
    fake = FakeOllamaClient({
        "is_strategy_picks": True, "direction": "buy", "count": 5,
        "named_strategy": None, "unrecognized_strategy_text": None,
    })
    intent = strategy_picks.detect("give me the top 5 buys from my strategies", [], client=fake)
    assert intent["is_strategy_picks"] is True
    assert intent["direction"] == "buy"
    assert intent["count"] == 5


# --- detect(): phrasing-agnostic recognition (033-strategy-picks-filters US2) --

def test_detect_recognizes_no_keyword_buy_and_short_phrasing():
    """User Story 2's concrete failing example — no "strategy"/"The Strat"/
    "Gap Analysis"/"Market Flow" keyword anywhere, but still a strategy-picks
    question."""
    fake = FakeOllamaClient({
        "is_strategy_picks": True, "direction": None, "count": 10,
        "named_strategy": None, "unrecognized_strategy_text": None, "extra_conditions": None,
    })
    intent = strategy_picks.detect("give me 10 stocks to buy and 10 to short", [], client=fake)
    assert intent["is_strategy_picks"] is True


def test_detect_recognizes_portfolio_phrasing_without_keyword():
    fake = FakeOllamaClient({
        "is_strategy_picks": True, "direction": "buy", "count": None,
        "named_strategy": None, "unrecognized_strategy_text": None, "extra_conditions": None,
    })
    intent = strategy_picks.detect("what should I add to my portfolio this week", [], client=fake)
    assert intent["is_strategy_picks"] is True


def test_detect_ordinary_screener_question_is_not_strategy_picks():
    """FR-009 regression guard: an ordinary screener-shaped question must
    still classify as false even under the broadened prompt."""
    fake = FakeOllamaClient({
        "is_strategy_picks": False, "direction": None, "count": None,
        "named_strategy": None, "unrecognized_strategy_text": None, "extra_conditions": None,
    })
    intent = strategy_picks.detect("what stocks have improving financials", [], client=fake)
    assert intent["is_strategy_picks"] is False


def test_detect_extracts_extra_conditions():
    fake = FakeOllamaClient({
        "is_strategy_picks": True, "direction": "buy", "count": None,
        "named_strategy": None, "unrecognized_strategy_text": None,
        "extra_conditions": ["only stocks I've liked", "in the consumer staples sector"],
    })
    intent = strategy_picks.detect(
        "what should I buy this week using only liked stocks in consumer staples", [], client=fake,
    )
    assert intent["extra_conditions"] == ["only stocks I've liked", "in the consumer staples sector"]


def test_detect_includes_history_in_the_prompt():
    fake = FakeOllamaClient({
        "is_strategy_picks": True, "direction": None, "count": None,
        "named_strategy": None, "unrecognized_strategy_text": None,
    })
    history = [
        {"role": "user", "content": "per my trading strategies what should I buy this week"},
        {"role": "assistant", "content": "Here are your buy picks..."},
    ]
    strategy_picks.detect("just show me the Gap Analysis ones", history, client=fake)
    prompt_text = fake.calls[0]["messages"][-1]["content"]
    assert "Gap Analysis ones" in prompt_text
    assert "buy this week" in prompt_text


# --- narrate(): fallback on LLM failure --------------------------------------

def test_narrate_falls_back_when_llm_unavailable(db):
    db[STRATEGY_SIGNALS].insert_one(signals_doc("AAPL", the_strat=strat_doc("AAPL", entry_price=187.5)))
    picks = strategy_picks.compute_picks("buy", 10, db)
    answer = strategy_picks.narrate("what should I buy", picks, client=FailingOllamaClient())
    assert "AAPL" in answer
    assert "187.5" in answer
    assert strategy_picks.DISCLAIMER in answer


# --- answer_strategy_picks(): full orchestration -----------------------------

def test_answer_strategy_picks_happy_path_includes_disclaimer(db, monkeypatch):
    db[STRATEGY_SIGNALS].insert_one(signals_doc("AAPL", the_strat=strat_doc("AAPL", entry_price=187.5)))
    fake = FakeOllamaClient(
        {"is_strategy_picks": True, "direction": "buy", "count": None,
         "named_strategy": None, "unrecognized_strategy_text": None},
        answer_text=f"AAPL at 187.5. {strategy_picks.DISCLAIMER}",
    )
    result = strategy_picks.answer_strategy_picks(
        "per my trading strategies what should I buy this week", [], db, client=fake,
    )
    assert result["strategy_picks"] is not None
    assert result["strategy_picks"]["direction"] == "buy"
    assert strategy_picks.DISCLAIMER in result["answer"]
    assert result["match_count"] == 1


def test_answer_strategy_picks_defaults_direction_when_unspecified(db):
    fake = FakeOllamaClient({
        "is_strategy_picks": True, "direction": None, "count": None,
        "named_strategy": None, "unrecognized_strategy_text": None,
    })
    result = strategy_picks.answer_strategy_picks("what should I do this week", [], db, client=fake)
    assert result["strategy_picks"]["direction"] == "buy"


def test_answer_strategy_picks_unrecognized_strategy_lists_supported_ones(db):
    fake = FakeOllamaClient({
        "is_strategy_picks": True, "direction": "buy", "count": None,
        "named_strategy": "unrecognized", "unrecognized_strategy_text": "my momentum strategy",
    })
    result = strategy_picks.answer_strategy_picks(
        "what does my momentum strategy say to buy", [], db, client=fake,
    )
    assert result["strategy_picks"] is None
    assert "my momentum strategy" in result["answer"]
    assert "The Strat" in result["answer"]
    assert "Gap Analysis" in result["answer"]


def test_answer_strategy_picks_narrows_to_named_strategy_on_follow_up(db):
    """US3: 'just show me the Gap Analysis ones' after a full picks answer
    filters the response to just that strategy's list, from the same
    underlying computation — not a different one."""
    db[STRATEGY_SIGNALS].insert_many([
        signals_doc("AAPL", the_strat=strat_doc("AAPL", entry_price=187.5)),
        signals_doc("MSFT", gap_analysis=gap_doc("MSFT", entry_price=412.0)),
    ])
    fake = FakeOllamaClient({
        "is_strategy_picks": True, "direction": "buy", "count": None,
        "named_strategy": "gap_analysis", "unrecognized_strategy_text": None,
    })
    history = [
        {"role": "user", "content": "per my trading strategies what should I buy this week"},
        {"role": "assistant", "content": "The Strat: AAPL at 187.5. Gap Analysis: MSFT at 412.0."},
    ]

    result = strategy_picks.answer_strategy_picks(
        "just show me the Gap Analysis ones", history, db, client=fake,
    )

    assert result["strategy_picks"] is not None
    assert [entry["strategy"] for entry in result["strategy_picks"]["lists"]] == ["gap_analysis"]
    assert result["match_count"] == 1


def test_answer_strategy_picks_applies_extra_condition_and_narrows_candidates(db):
    """US1 AS1/AS2: a strategy-picks question naming an extra condition is
    translated via condition_filter and used to narrow the candidate set
    before ranking."""
    db[STRATEGY_SIGNALS].insert_many([
        signals_doc("KO", the_strat=strat_doc("KO", entry_price=61.2)),
        signals_doc("AAPL", the_strat=strat_doc("AAPL", entry_price=190.0)),
    ])
    db[SCREENER].insert_many([
        {"ticker": "KO", "liked_status": "liked"},
        {"ticker": "AAPL", "liked_status": None},
    ])
    fake = MultiCallFakeClient([
        {"is_strategy_picks": True, "direction": "buy", "count": None,
         "named_strategy": None, "unrecognized_strategy_text": None,
         "extra_conditions": ["only stocks I've liked"]},
        {"collection": "screener", "pipeline": [{"$match": {"liked_status": "liked"}}], "in_scope": True},
    ], answer_text=f"KO at 61.2 (liked). {strategy_picks.DISCLAIMER}")

    result = strategy_picks.answer_strategy_picks(
        "per my trading strategies what should I buy this week using only stocks I've liked",
        [], db, client=fake,
    )

    picks = result["strategy_picks"]
    assert picks["condition_requested"] == "only stocks I've liked"
    assert picks["condition_applied"] is True
    assert picks["condition_note"] is None
    the_strat = next(e for e in picks["lists"] if e["strategy"] == "the_strat")
    assert [c["ticker"] for c in the_strat["candidates"]] == ["KO"]
    assert result["criteria"] == [
        {"label": "liked_status = liked", "field": "liked_status", "op": "=", "value": "liked"},
    ]


def test_answer_strategy_picks_two_conditions_anded(db):
    """US1 AS5: two conditions in the same question are combined with AND —
    a candidate must satisfy both to appear."""
    db[STRATEGY_SIGNALS].insert_many([
        signals_doc("KO", the_strat=strat_doc("KO", entry_price=61.2)),
        signals_doc("PG", the_strat=strat_doc("PG", entry_price=150.0)),
    ])
    db[SCREENER].insert_many([
        {"ticker": "KO", "liked_status": "liked", "sector": "Consumer Staples"},
        {"ticker": "PG", "liked_status": "liked", "sector": "Technology"},
    ])
    fake = MultiCallFakeClient([
        {"is_strategy_picks": True, "direction": "buy", "count": None,
         "named_strategy": None, "unrecognized_strategy_text": None,
         "extra_conditions": ["only stocks I've liked", "in the consumer staples sector"]},
        {"collection": "screener",
         "pipeline": [{"$match": {"liked_status": "liked", "sector": "Consumer Staples"}}],
         "in_scope": True},
    ])

    result = strategy_picks.answer_strategy_picks(
        "per my strategies give me liked stocks in the consumer staples sector to buy this week",
        [], db, client=fake,
    )

    the_strat = next(e for e in result["strategy_picks"]["lists"] if e["strategy"] == "the_strat")
    assert [c["ticker"] for c in the_strat["candidates"]] == ["KO"]
    assert len(result["criteria"]) == 2


def test_answer_strategy_picks_zero_match_condition_states_note_naming_it(db):
    """FR-006/US1 AS3: a real zero-match result under an extra condition
    states so plainly in that strategy's note, naming the condition."""
    db[STRATEGY_SIGNALS].insert_one(signals_doc("AAPL", the_strat=strat_doc("AAPL")))
    db[SCREENER].insert_one({"ticker": "AAPL", "liked_status": None})
    fake = MultiCallFakeClient([
        {"is_strategy_picks": True, "direction": "buy", "count": None,
         "named_strategy": None, "unrecognized_strategy_text": None,
         "extra_conditions": ["only stocks I've liked"]},
        {"collection": "screener", "pipeline": [{"$match": {"liked_status": "liked"}}], "in_scope": True},
    ])

    result = strategy_picks.answer_strategy_picks(
        "what should I buy this week using only liked stocks", [], db, client=fake,
    )

    picks = result["strategy_picks"]
    assert picks["condition_applied"] is True
    the_strat = next(e for e in picks["lists"] if e["strategy"] == "the_strat")
    assert the_strat["candidates"] == []
    assert "only stocks I've liked" in the_strat["note"]


def test_answer_strategy_picks_ambiguous_condition_discloses_interpretation(db):
    """FR-008: translation succeeds with a non-literal field mapping — the
    response still applies the condition but discloses which reading was
    used, via a non-null condition_note."""
    db[STRATEGY_SIGNALS].insert_one(signals_doc("AAPL", the_strat=strat_doc("AAPL", entry_price=190.0)))
    db[SCREENER].insert_one({"ticker": "AAPL", "liked_status": None, "market_cap": 3_000_000_000_000})
    fake = MultiCallFakeClient([
        {"is_strategy_picks": True, "direction": "buy", "count": None,
         "named_strategy": None, "unrecognized_strategy_text": None,
         "extra_conditions": ["large cap stocks"]},
        {"collection": "screener",
         "pipeline": [{"$match": {"market_cap": {"$gt": 10_000_000_000}}}], "in_scope": True},
    ])

    result = strategy_picks.answer_strategy_picks(
        "what large cap stocks should I buy this week per my strategies", [], db, client=fake,
    )

    picks = result["strategy_picks"]
    assert picks["condition_applied"] is True
    assert picks["condition_note"] is not None
    assert "large cap stocks" in picks["condition_note"]
    the_strat = next(e for e in picks["lists"] if e["strategy"] == "the_strat")
    assert [c["ticker"] for c in the_strat["candidates"]] == ["AAPL"]


def test_answer_strategy_picks_market_flow_named_explains_the_filter_role(db):
    fake = FakeOllamaClient({
        "is_strategy_picks": True, "direction": "buy", "count": None,
        "named_strategy": "market_flow", "unrecognized_strategy_text": None,
    })
    result = strategy_picks.answer_strategy_picks(
        "what are my Market Flow picks this week", [], db, client=fake,
    )
    assert result["strategy_picks"] is None
    assert "Market Flow" in result["answer"]
    assert "filter" in result["answer"]

"""Tests for condition_filter.translate_conditions().
Spec: specs/033-strategy-picks-filters; data-model.md; research.md R4.

Mirrors test_chat_router.py's FakeOllamaClient injection pattern — client is
passed explicitly rather than monkeypatching llm.get_client().
"""
import json

from db import SCREENER
from semantic import condition_filter


class FakeOllamaClient:
    def __init__(self, query_response: dict):
        self.query_response = query_response
        self.calls: list[dict] = []

    def chat(self, *, model, messages, format=None, think=None, keep_alive=None, options=None):
        self.calls.append({"messages": messages, "format": format})
        return {"message": {"content": json.dumps(self.query_response)}}


class FailingOllamaClient:
    def chat(self, **kwargs):
        raise ConnectionError("ollama unreachable")


def screener_doc(ticker, **overrides):
    doc = {"ticker": ticker, "liked_status": None, "sector": "Technology"}
    doc.update(overrides)
    return doc


def test_single_condition_applied_successfully(db):
    db[SCREENER].insert_many([
        screener_doc("KO", liked_status="liked"),
        screener_doc("PEP", liked_status=None),
    ])
    fake = FakeOllamaClient({
        "collection": "screener",
        "pipeline": [{"$match": {"liked_status": "liked"}}],
        "in_scope": True,
    })

    result = condition_filter.translate_conditions(["only stocks I've liked"], db, client=fake)

    assert result["applied"] is True
    assert result["tickers"] == {"KO"}
    assert result["note"] is None
    assert result["criteria"] == [
        {"label": "liked_status = liked", "field": "liked_status", "op": "=", "value": "liked"},
    ]


def test_two_conditions_anded_into_one_pipeline(db):
    db[SCREENER].insert_many([
        screener_doc("KO", liked_status="liked", sector="Consumer Staples"),
        screener_doc("PG", liked_status="liked", sector="Consumer Staples"),
        screener_doc("AAPL", liked_status="liked", sector="Technology"),
    ])
    fake = FakeOllamaClient({
        "collection": "screener",
        "pipeline": [{"$match": {"liked_status": "liked", "sector": "Consumer Staples"}}],
        "in_scope": True,
    })

    result = condition_filter.translate_conditions(
        ["only stocks I've liked", "in the consumer staples sector"], db, client=fake,
    )

    assert result["applied"] is True
    assert result["tickers"] == {"KO", "PG"}
    # both conditions were joined into a single prompt, not one call per condition
    assert len(fake.calls) == 1
    prompt_text = fake.calls[0]["messages"][-1]["content"]
    assert "only stocks I've liked" in prompt_text
    assert "in the consumer staples sector" in prompt_text


def test_legitimate_zero_match_is_applied_true_with_empty_set(db):
    db[SCREENER].insert_many([screener_doc("KO", liked_status="disliked")])
    fake = FakeOllamaClient({
        "collection": "screener",
        "pipeline": [{"$match": {"liked_status": "liked"}}],
        "in_scope": True,
    })

    result = condition_filter.translate_conditions(["only stocks I've liked"], db, client=fake)

    assert result["applied"] is True
    assert result["tickers"] == set()
    assert result["note"] is None


def test_in_scope_false_yields_applied_false(db):
    fake = FakeOllamaClient({"collection": "screener", "pipeline": [], "in_scope": False})

    result = condition_filter.translate_conditions(["most popular stocks"], db, client=fake)

    assert result["applied"] is False
    assert result["tickers"] is None
    assert result["criteria"] == []
    assert result["note"] is not None


def test_llm_error_yields_applied_false(db):
    result = condition_filter.translate_conditions(
        ["only stocks I've liked"], db, client=FailingOllamaClient(),
    )

    assert result["applied"] is False
    assert result["tickers"] is None
    assert result["note"] is not None


def test_query_rejected_yields_applied_false(db):
    db[SCREENER].insert_many([screener_doc("KO")])
    fake = FakeOllamaClient({
        "collection": "screener",
        "pipeline": [{"$out": "some_other_collection"}],
        "in_scope": True,
    })

    result = condition_filter.translate_conditions(["delete everything"], db, client=fake)

    assert result["applied"] is False
    assert result["tickers"] is None
    assert result["note"] is not None
    # the DB must be untouched
    assert db[SCREENER].count_documents({}) == 1


# --- US3: unanswerable / ambiguous conditions --------------------------------

def test_unanswerable_condition_names_what_could_not_be_applied(db):
    """US3 AS1, contract's FR-007 example: a condition with no corresponding
    data field yields applied: False and a note naming exactly what
    couldn't be applied."""
    fake = FakeOllamaClient({"collection": "screener", "pipeline": [], "in_scope": False})

    result = condition_filter.translate_conditions(
        ["most popular in consumer staples"], db, client=fake,
    )

    assert result["applied"] is False
    assert result["tickers"] is None
    assert "most popular in consumer staples" in result["note"]
    assert "doesn't correspond to any field" in result["note"]


def test_ambiguous_condition_applies_with_disclosed_interpretation(db):
    """FR-008: a condition with no literal field name but a reasonable
    stand-in interpretation still applies — with a note disclosing which
    reading was used, rather than silently substituting it."""
    db[SCREENER].insert_many([
        screener_doc("AAPL", market_cap=3_000_000_000_000),
        screener_doc("SMOL", market_cap=50_000_000),
    ])
    fake = FakeOllamaClient({
        "collection": "screener",
        "pipeline": [{"$match": {"market_cap": {"$gt": 10_000_000_000}}}],
        "in_scope": True,
    })

    result = condition_filter.translate_conditions(["large cap stocks"], db, client=fake)

    assert result["applied"] is True
    assert result["tickers"] == {"AAPL"}
    assert result["note"] is not None
    assert "large cap stocks" in result["note"]
    assert "market_cap" in result["note"]


def test_display_stages_are_stripped_before_execution(db):
    """research.md R4 — a $sort/$limit/$project the model emits must not
    truncate the ticker membership set; with a $limit of 1, a naive
    execution would only return one ticker even though two qualify."""
    db[SCREENER].insert_many([
        screener_doc("AAAA", liked_status="liked"),
        screener_doc("ZZZZ", liked_status="liked"),
    ])
    fake = FakeOllamaClient({
        "collection": "screener",
        "pipeline": [
            {"$match": {"liked_status": "liked"}},
            {"$sort": {"ticker": 1}},
            {"$limit": 1},
        ],
        "in_scope": True,
    })

    result = condition_filter.translate_conditions(["only stocks I've liked"], db, client=fake)

    assert result["applied"] is True
    assert result["tickers"] == {"AAAA", "ZZZZ"}

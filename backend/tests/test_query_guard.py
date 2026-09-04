"""Read-only enforcement for chat-generated MongoDB pipelines.
Spec: specs/031-semantic-layer-chat; contracts/chat-api.md (Read-only guarantee).

MongoDB auth is disabled in this deployment (research.md R6), so this
allowlist is the *only* real enforcement — there is no database-level
read-only role behind it. These tests are the actual assurance that a
model-generated pipeline cannot mutate data, not a formality.
"""
import pytest

from semantic.query_guard import (
    DEFAULT_LIMIT,
    DEFAULT_MAX_TIME_MS,
    HARD_LIMIT_CAP,
    QueryRejected,
    validate_pipeline,
)


def test_simple_match_is_accepted():
    pipeline = validate_pipeline([{"$match": {"zscore_20d": {"$lt": 0}}}])
    assert pipeline[-1] == {"$limit": DEFAULT_LIMIT}


def test_limit_is_injected_when_absent():
    pipeline = validate_pipeline([{"$match": {}}])
    assert pipeline[-1] == {"$limit": DEFAULT_LIMIT}


def test_existing_limit_under_cap_is_preserved():
    pipeline = validate_pipeline([{"$match": {}}, {"$limit": 10}])
    assert {"$limit": 10} in pipeline
    assert pipeline.count({"$limit": DEFAULT_LIMIT}) == 0


def test_limit_over_hard_cap_is_rejected():
    with pytest.raises(QueryRejected):
        validate_pipeline([{"$match": {}}, {"$limit": HARD_LIMIT_CAP + 1}])


@pytest.mark.parametrize("stage", ["$out", "$merge", "$function", "$accumulator", "$where", "$graphLookup"])
def test_write_or_escape_capable_stages_are_rejected(stage):
    with pytest.raises(QueryRejected):
        validate_pipeline([{stage: {}}])


def test_unrecognized_dollar_stage_is_rejected():
    with pytest.raises(QueryRejected):
        validate_pipeline([{"$madeUpStage": {}}])


def test_non_screener_collection_target_is_rejected():
    with pytest.raises(QueryRejected):
        validate_pipeline([{"$match": {}}], collection="price_history")


def test_screener_collection_target_is_accepted():
    validate_pipeline([{"$match": {}}], collection="screener")


def test_allowlisted_stages_pass_through():
    pipeline = [
        {"$match": {"sector": "Technology"}},
        {"$project": {"ticker": 1}},
        {"$sort": {"ticker": 1}},
        {"$group": {"_id": "$sector", "n": {"$sum": 1}}},
        {"$limit": 5},
    ]
    result = validate_pipeline(list(pipeline))
    assert result[:-1] == pipeline[:-1]  # last $limit stays as given (under cap)


def test_empty_pipeline_gets_a_default_limit():
    pipeline = validate_pipeline([])
    assert pipeline == [{"$limit": DEFAULT_LIMIT}]


def test_non_list_pipeline_is_rejected():
    with pytest.raises(QueryRejected):
        validate_pipeline("not a list")


def test_stage_that_is_not_a_single_key_dict_is_rejected():
    with pytest.raises(QueryRejected):
        validate_pipeline([{"$match": {}, "$sort": {}}])


def test_out_smuggled_as_a_non_first_stage_is_still_rejected():
    with pytest.raises(QueryRejected):
        validate_pipeline([{"$match": {}}, {"$out": "some_collection"}])


# --- 15x-scale enforcement (US4, research.md R5) ---
# The scale question was answered empirically for size/latency via
# scripts/seed_15x_screener.py against a real MongoDB instance (5.12 MB data,
# 3.6ms flagship-style query at 8,340 docs — comfortably real, not
# mongomock). What's left to prove here is that the $limit/maxTimeMS bounds
# this module injects actually constrain execution against a large result
# set, not just that they're present in the returned pipeline.

def test_limit_actually_bounds_execution_against_a_large_collection(db):
    db["screener"].insert_many([{"ticker": f"SYN{i:05d}", "zscore_20d": -1} for i in range(2000)])

    pipeline = validate_pipeline([{"$match": {"zscore_20d": {"$lt": 0}}}])
    results = list(db["screener"].aggregate(pipeline, maxTimeMS=DEFAULT_MAX_TIME_MS))

    assert len(results) == DEFAULT_LIMIT  # not 2000 — the injected $limit did its job


# --- 035-chat-and-news-upgrade US3 (FR-010, research.md R2/R3) — a second
# readable collection, and the $text-must-be-first-stage rule that goes with it.

def test_news_articles_collection_target_is_accepted():
    validate_pipeline([{"$match": {}}], collection="news_articles")


def test_text_search_as_the_first_stage_is_accepted():
    pipeline = validate_pipeline(
        [{"$match": {"$text": {"$search": "tariffs"}}}], collection="news_articles",
    )
    assert pipeline[0] == {"$match": {"$text": {"$search": "tariffs"}}}


def test_text_search_in_a_non_first_stage_is_rejected():
    with pytest.raises(QueryRejected):
        validate_pipeline(
            [{"$match": {"tickers": "NVDA"}}, {"$match": {"$text": {"$search": "tariffs"}}}],
            collection="news_articles",
        )


def test_text_search_nested_inside_a_compound_first_match_is_still_first_stage_ok():
    pipeline = validate_pipeline(
        [{"$match": {"$text": {"$search": "tariffs"}}, }, {"$sort": {"published_at": -1}}],
        collection="news_articles",
    )
    assert pipeline[0]["$match"].get("$text") == {"$search": "tariffs"}


def test_a_collection_still_not_in_the_allowlist_is_rejected():
    with pytest.raises(QueryRejected):
        validate_pipeline([{"$match": {}}], collection="chat_conversations")


def test_hard_cap_rejected_pipeline_is_never_executed(db):
    db["screener"].insert_many([{"ticker": f"SYN{i:05d}"} for i in range(500)])

    with pytest.raises(QueryRejected):
        validate_pipeline([{"$match": {}}, {"$limit": HARD_LIMIT_CAP + 50}])
    # the point: a caller that catches QueryRejected never reaches .aggregate()
    # at all, so there's no scenario where an over-cap query actually runs

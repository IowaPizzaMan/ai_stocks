"""Chat orchestration: question -> generated query -> validated -> executed -> interpreted.
Spec: specs/031-semantic-layer-chat; contracts/chat-api.md.

Two Ollama calls per question, deliberately: query generation wants
temperature=0 and constrained decoding; answer interpretation wants prose.
Conversation context (FR-003/FR-004) is replayed text, not a stored session
— the client resends history each turn and nothing is persisted server-side
(research.md R9). A follow-up like "which of those has the highest market
cap" works because the interpretation step is instructed to name actual
tickers in its answer, so they're recoverable from the replayed history text
without any extra state.
"""
from datetime import datetime, timezone

from pymongo.database import Database

import llm
from db import NEWS_ARTICLES, SCREENER
from logging_config import get_logger
from semantic import conversations, news_rank, strategy_picks
from semantic.linkify import linkify_citation, linkify_tickers
from semantic.query_guard import DEFAULT_MAX_TIME_MS, QueryRejected, validate_pipeline
from semantic.screener_query import coerce_news_search, criteria_from_pipeline, generate_pipeline

# 036-news-semantic-search — appended to the answer when the semantic ranker
# was unavailable and chat fell back to the model's keyword pipeline (FR-011;
# contracts/chat-news-retrieval.md §4).
SEMANTIC_UNAVAILABLE_NOTE = "(Ranked by keyword match — semantic search was unavailable.)"

logger = get_logger(__name__)

# Server-side cap on replayed conversation context (research.md R9) — without
# one, a long conversation grows the prompt until latency regresses past
# SC-001.
MAX_HISTORY_TURNS = 6


def _format_history(history: list[dict]) -> str:
    if not history:
        return ""
    trimmed = history[-MAX_HISTORY_TURNS:]
    lines = [f"{turn.get('role')}: {turn.get('content')}" for turn in trimmed]
    return "Conversation so far:\n" + "\n".join(lines) + "\n\n"


def _latest_signals_as_of(db: Database):
    doc = db[SCREENER].find_one(sort=[("signals_as_of", -1)], projection={"signals_as_of": 1})
    return doc["signals_as_of"] if doc else None


def _known_tickers(db: Database) -> set[str]:
    """The tracked-ticker universe (research.md R5) — the same one already
    used elsewhere (watchlist, stock pages). Read fresh per question rather
    than cached: screener's ticker set changes as tickers are added/removed,
    and this call is cheap (an indexed distinct)."""
    return set(db[SCREENER].distinct("ticker"))


def _format_answer_prompt(question: str, rows: list[dict], criteria: list[dict],
                          collection: str = SCREENER) -> str:
    criteria_text = "; ".join(c["label"] for c in criteria) or "no specific filter"
    preview = rows[:20]
    if collection == NEWS_ARTICLES:
        return (
            f"User asked: {question}\n\n"
            f"Query filtered on: {criteria_text}\n"
            f"Found {len(rows)} stored news stories. Stories:\n{preview}\n\n"
            "Write a natural-language answer that references the specific "
            "stored stories by their actual headline and date (FR-008) — "
            "do not invent a headline or detail that isn't in the stories "
            "above. If there are no stories, say plainly that no relevant "
            "news was found rather than fabricating one (FR-009)."
        )
    return (
        f"User asked: {question}\n\n"
        f"Query filtered on: {criteria_text}\n"
        f"Matched {len(rows)} stocks. Rows:\n{preview}\n\n"
        "Write a thorough, detailed natural-language answer summarizing the "
        "findings. Name actual tickers, and discuss notable individual stocks "
        "(e.g. standout metrics, how they compare to each other, any patterns "
        "across the matches). If there are no matches, say so plainly rather "
        "than inventing results."
    )


def _fallback_answer(rows: list[dict], collection: str = SCREENER) -> str:
    """Used only if the interpretation call itself fails — the data is real,
    only the prose is templated, so this is still a truthful (if terse)
    answer rather than an error."""
    if collection == NEWS_ARTICLES:
        if not rows:
            return "No relevant news was found."
        headlines = "; ".join(r.get("title", "?") for r in rows[:15])
        return f"{len(rows)} stories found: {headlines}"
    if not rows:
        return "No stocks matched that criteria."
    tickers = ", ".join(r.get("ticker", "?") for r in rows[:15])
    return f"{len(rows)} stocks matched: {tickers}"


def _empty_response(answer: str, *, note: str, degraded: bool, signals_as_of=None,
                    generated_query=None) -> dict:
    return {
        "answer": answer, "criteria": [], "match_count": 0, "rows": [],
        "generated_query": generated_query, "excluded_for_missing_data": 0,
        "signals_as_of": signals_as_of, "degraded": degraded, "note": note,
        # 032-weekly-strategy-picks — additive field, null for every response
        # from this (031's original) free-form flow.
        "strategy_picks": None,
        # 035-chat-and-news-upgrade — additive field, empty whenever no news
        # question was actually answered.
        "citations": [],
    }


def _citations_from_rows(collection: str, rows: list[dict]) -> list[dict]:
    """FR-008 — when the answer drew on news_articles, cite the specific
    stored stories rather than an unsupported claim. Empty for every other
    collection (nothing to cite)."""
    if collection != NEWS_ARTICLES:
        return []
    citations = []
    for row in rows:
        if not row.get("title") or not row.get("url"):
            continue
        citations.append({
            "title": row["title"],
            "url": row["url"],
            "published_date": row.get("published_date"),
            "publisher": row.get("publisher"),
        })
    return citations


def _append_citations(answer_text: str, citations: list[dict]) -> str:
    """Renders each citation as a clickable markdown link and appends them —
    deterministic linking (constitution III) rather than asking the model to
    place the links itself, which FR-014 explicitly does not trust it to do
    correctly for tickers and is no more trustworthy for citations."""
    if not citations:
        return answer_text
    sources = "\n".join(
        f"- {linkify_citation(c['title'], c['url'])}" for c in citations
    )
    return f"{answer_text}\n\nSources:\n{sources}"


def answer_question(question: str, history: list[dict], db: Database, *, client=None,
                    conversation_id: str | None = None) -> dict:
    """Computes the answer, then persists the exchange (US5, FR-015) — a
    thin wrapper so persistence covers every response shape uniformly
    (strategy-picks included) without duplicating it into each branch below."""
    response = _generate_answer(question, history, db, client=client)
    return _attach_conversation(question, response, db, client=client, conversation_id=conversation_id)


def _attach_conversation(question: str, response: dict, db: Database, *, client=None,
                         conversation_id: str | None = None) -> dict:
    # A degraded response (no_data/model_unavailable/out_of_scope/
    # query_rejected) isn't a real exchange worth a history entry or a title
    # LLM call — data-model.md's "at least one complete exchange" rule.
    if response.get("degraded"):
        response["conversation_id"] = None
        response["conversation_title"] = None
        return response

    # Persistence failure must never cost the user the answer they waited on
    # (contracts/chat-history-api.md) — deliberately broad except: a Mongo
    # write can fail in more ways than are worth enumerating here, and every
    # one of them should degrade to "no conversation saved", not a 500.
    try:
        if conversation_id:
            conversations.append(conversation_id, question, response["answer"], db)
            response["conversation_id"] = conversation_id
            response["conversation_title"] = None
        else:
            created = conversations.create(question, response["answer"], db, client=client)
            response["conversation_id"] = str(created["_id"])
            response["conversation_title"] = created["title"]
    except Exception as exc:
        logger.warning("conversation persistence failed: %s", exc)
        response["conversation_id"] = None
        response["conversation_title"] = None
    return response


def _generate_answer(question: str, history: list[dict], db: Database, *, client=None) -> dict:
    # 032-weekly-strategy-picks — checked first, and before the screener-
    # emptiness check below: a strategy-picks question reads `strategy_signals`,
    # not `screener`, so it must not be gated on screener data existing.
    # 033-strategy-picks-filters FR-001 — detect() now runs on every question
    # (no keyword pre-filter): no fixed keyword list can reliably recognize
    # strategy-picks phrasing (research.md R2). The added latency on an
    # ordinary screener question is an explicitly accepted tradeoff (spec
    # Assumptions). If intent detection itself fails, that's treated the
    # same as "not a strategy-picks question" — the existing flow below has
    # its own model-unavailable path.
    try:
        intent = strategy_picks.detect(question, history, client=client)
    except llm.LLMError as exc:
        logger.warning("strategy_picks intent detection failed: %s", exc)
        intent = {"is_strategy_picks": False}
    if intent.get("is_strategy_picks"):
        return strategy_picks.answer_strategy_picks(
            question, history, db, client=client, intent=intent,
        )

    try:
        generated = generate_pipeline(
            _format_history(history) + f"Question: {question}", client=client,
        )
    except llm.LLMError as exc:
        logger.warning("chat query generation failed: %s", exc)
        return _empty_response(
            "The chat model is temporarily unavailable — please try again.",
            note="model_unavailable", degraded=True,
        )

    if not generated.get("in_scope", True):
        return _empty_response(
            "I can't answer that with the data I have available — I only "
            "have pre-computed price/financial screening signals and stored "
            "news for tracked stocks.",
            note="out_of_scope", degraded=False,
            signals_as_of=_latest_signals_as_of(db),
        )

    collection = generated.get("collection") or SCREENER
    raw_pipeline = generated.get("pipeline") or []

    # 035-chat-and-news-upgrade — collection-aware now that a question might
    # target news_articles instead of screener: an empty screener must not
    # block a news question that has real data to answer from (research.md
    # R2's multi-collection fix). Moved here (after the collection is known)
    # from before generate_pipeline() — the earlier position predates a
    # second readable collection existing at all.
    if db[collection].find_one() is None:
        return _empty_response(
            f"I don't have any data in {collection} yet — the background "
            "worker hasn't populated it. Try again after the next refresh cycle.",
            note="no_data", degraded=True,
        )

    # 036-news-semantic-search — for a news question the model also picks a
    # retrieval mode. `semantic` ranks by meaning via news_rank; `recency`
    # runs the generated pipeline exactly as before. A missing news_search is
    # coerced to recency (contracts/chat-news-retrieval.md §1).
    news_search = None
    degradation_note = None
    if collection == NEWS_ARTICLES:
        news_search = coerce_news_search(
            generated.get("news_search"), question=question,
            known_tickers=_known_tickers(db),
        )
        if news_search["mode"] == "semantic":
            try:
                ranked = news_rank.rank_articles(
                    db, news_search, client=client, now=datetime.now(timezone.utc),
                )
            except llm.LLMError as exc:
                # FR-011 — embedding unavailable: fall through to the model's
                # generated keyword pipeline with a note, never a 500.
                logger.warning("semantic news rank unavailable — keyword fallback: %s", exc)
                degradation_note = SEMANTIC_UNAVAILABLE_NOTE
            else:
                return _news_semantic_response(
                    question, ranked, news_search, db, raw_pipeline, client=client,
                )

    try:
        pipeline = validate_pipeline(raw_pipeline, collection=collection)
    except QueryRejected as exc:
        logger.warning("chat query rejected: %s", exc)
        return _empty_response(
            "I couldn't answer that safely — the generated query wasn't "
            "allowed. Try rephrasing the question.",
            note="query_rejected", degraded=False,
            signals_as_of=_latest_signals_as_of(db),
            generated_query={"collection": collection, "pipeline": raw_pipeline},
        )

    # 035-chat-and-news-upgrade US3 (research.md R2) — execute against the
    # collection the model actually chose and query_guard validated, not a
    # hardcoded SCREENER. Dormant until READABLE_COLLECTIONS grew past
    # {"screener"}; live now that news_articles is admitted.
    rows = list(db[collection].aggregate(pipeline, maxTimeMS=DEFAULT_MAX_TIME_MS))
    # 035-chat-and-news-upgrade US1 — a $group stage repurposes `_id` as the
    # group key (e.g. a sector name), not a Mongo document id; stripping it
    # unconditionally would silently discard the one field an aggregation
    # answer is actually about.
    is_grouped = any("$group" in stage for stage in pipeline)
    if not is_grouped:
        for row in rows:
            row.pop("_id", None)

    excluded = sum(1 for r in rows if r.get("insufficient_history"))
    criteria = criteria_from_pipeline(pipeline)
    citations = _citations_from_rows(collection, rows)

    try:
        answer_text = llm.generate_text(
            prompt=_format_answer_prompt(question, rows, criteria, collection),
            client=client,
            options={"temperature": 0.2},
        )
    except llm.LLMError as exc:
        logger.warning("chat answer interpretation failed, using fallback: %s", exc)
        answer_text = _fallback_answer(rows, collection)

    # 035-chat-and-news-upgrade US4 (FR-013) — applies to both the
    # screener-match and news-search flows above; not to strategy_picks
    # (returned earlier), whose candidates are already structured data
    # linked directly in the frontend.
    answer_text = linkify_tickers(answer_text, _known_tickers(db))
    if degradation_note:
        answer_text = f"{answer_text}\n\n{degradation_note}"
    answer_text = _append_citations(answer_text, citations)

    return {
        "answer": answer_text,
        "criteria": criteria,
        "match_count": len(rows),
        "rows": rows,
        "generated_query": {"collection": collection, "pipeline": pipeline,
                            "news_search": news_search},
        "excluded_for_missing_data": excluded,
        "signals_as_of": _latest_signals_as_of(db),
        "degraded": False,
        "note": None,
        "strategy_picks": None,
        "citations": citations,
    }


def _news_semantic_response(question: str, rows: list[dict], news_search: dict,
                            db: Database, raw_pipeline: list[dict], *, client=None) -> dict:
    """Builds the chat response from news_rank's ranked full documents — the
    same answer-interpretation + citation + ticker-linkify steps the pipeline
    path uses, just fed the semantically ranked rows instead of an
    aggregation's output (contracts/chat-news-retrieval.md §3 step 6). The
    model's generated `pipeline` is not executed here but is still carried on
    `generated_query` for transparency (031 FR-013)."""
    criteria = [{"label": f"semantic match: {news_search['query_text']}",
                 "field": "query_text", "op": "~", "value": news_search["query_text"]}]
    if news_search.get("ticker"):
        criteria.append({"label": f"tickers = {news_search['ticker']}",
                         "field": "tickers", "op": "=", "value": news_search["ticker"]})
    citations = _citations_from_rows(NEWS_ARTICLES, rows)

    try:
        answer_text = llm.generate_text(
            prompt=_format_answer_prompt(question, rows, criteria, NEWS_ARTICLES),
            client=client,
            options={"temperature": 0.2},
        )
    except llm.LLMError as exc:
        logger.warning("chat answer interpretation failed, using fallback: %s", exc)
        answer_text = _fallback_answer(rows, NEWS_ARTICLES)

    answer_text = linkify_tickers(answer_text, _known_tickers(db))
    answer_text = _append_citations(answer_text, citations)

    return {
        "answer": answer_text,
        "criteria": criteria,
        "match_count": len(rows),
        "rows": rows,
        "generated_query": {"collection": NEWS_ARTICLES, "pipeline": raw_pipeline,
                            "news_search": news_search},
        "excluded_for_missing_data": 0,
        "signals_as_of": _latest_signals_as_of(db),
        "degraded": False,
        "note": None,
        "strategy_picks": None,
        "citations": citations,
    }

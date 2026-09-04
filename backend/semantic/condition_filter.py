"""Translates a strategy-picks question's extra condition(s) into a ticker
set. Spec: specs/033-strategy-picks-filters; data-model.md; research.md R4.

Reuses `screener_query`'s exact question-to-pipeline mechanism (FR-004) —
not a hardcoded condition parser. The resulting pipeline still passes
through `query_guard.validate_pipeline()` for stage-allowlist safety, but
any `$sort`/`$limit`/`$project` stage the model emits is stripped before
execution: those stages exist to bound rows *displayed* to a user in the
free-form flow, and reusing them here would silently truncate the ticker
membership set this function computes (research.md R4).
"""
from pymongo.database import Database

import llm
from db import SCREENER
from logging_config import get_logger
from semantic import screener_query
from semantic.query_guard import QueryRejected, validate_pipeline

logger = get_logger(__name__)

_DISPLAY_STAGES = {"$sort", "$limit", "$project"}

_AMBIGUITY_INSTRUCTION = (
    " If a condition doesn't literally name a field, use the closest "
    "reasonable field and threshold (e.g. \"large cap\" -> market_cap over "
    "a reasonable threshold) rather than setting in_scope to false — but "
    "never invent or guess at a concept with no reasonable corresponding "
    "field (e.g. \"most popular\"), which must set in_scope to false."
)


def _format_prompt(conditions: list[str]) -> str:
    joined = "; ".join(conditions)
    return f"Question: stocks that are: {joined}.{_AMBIGUITY_INSTRUCTION}"


def _describe_interpretation(criteria: list[dict], combined_label: str) -> str | None:
    """FR-008 — when a resolved field's meaningful name components don't
    literally appear in what the user said, the mapping was an
    interpretation, not a literal match — disclose it rather than silently
    substitute it."""
    lowered = combined_label.lower()
    undisclosed = []
    for c in criteria:
        words = [w for w in c["field"].split("_") if len(w) >= 4]
        if words and not any(w in lowered for w in words):
            undisclosed.append(c["label"])
    if not undisclosed:
        return None
    return f"interpreted \"{combined_label}\" as {'; '.join(undisclosed)}"


def translate_conditions(conditions: list[str], db: Database, *, client=None) -> dict:
    """Returns a ConditionFilterResult:
    {"applied": bool, "tickers": set[str] | None, "criteria": list[dict],
    "note": str | None}. `conditions` is the non-empty extra_conditions list
    from a strategy-picks intent — joined into one prompt so multiple
    conditions produce a single AND'd pipeline (FR-004), not one call per
    condition."""
    combined_label = "; ".join(conditions)

    try:
        generated = screener_query.generate_pipeline(_format_prompt(conditions), client=client)
    except llm.LLMError as exc:
        logger.warning("condition_filter: translation call failed: %s", exc)
        return {
            "applied": False, "tickers": None, "criteria": [],
            "note": f"\"{combined_label}\" couldn't be evaluated right now — "
                    "answered without that condition.",
        }

    if not generated.get("in_scope", True):
        return {
            "applied": False, "tickers": None, "criteria": [],
            "note": f"\"{combined_label}\" doesn't correspond to any field "
                    "this system tracks — answered without that condition.",
        }

    raw_pipeline = generated.get("pipeline") or []
    try:
        validated_pipeline = validate_pipeline(raw_pipeline, collection="screener")
    except QueryRejected as exc:
        logger.warning("condition_filter: generated pipeline rejected: %s", exc)
        return {
            "applied": False, "tickers": None, "criteria": [],
            "note": f"\"{combined_label}\" couldn't be applied safely — "
                    "answered without that condition.",
        }

    match_stages = [stage for stage in validated_pipeline
                     if next(iter(stage)) not in _DISPLAY_STAGES]
    execution_pipeline = match_stages + [{"$project": {"_id": 0, "ticker": 1}}]

    cursor = db[SCREENER].aggregate(execution_pipeline)
    tickers = {row["ticker"] for row in cursor}

    criteria = screener_query.criteria_from_pipeline(match_stages)
    note = _describe_interpretation(criteria, combined_label)

    return {"applied": True, "tickers": tickers, "criteria": criteria, "note": note}

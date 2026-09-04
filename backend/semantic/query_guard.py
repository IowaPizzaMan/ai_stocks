"""Read-only enforcement for chat-generated MongoDB aggregation pipelines.
Spec: specs/031-semantic-layer-chat; contracts/chat-api.md (FR-012, FR-016).

MongoDB auth is NOT enabled in this deployment (research.md R6): no --auth,
no init script, credential-free connection strings everywhere. That means
this allowlist is application-code enforcement, not a database-level
permission — it cannot be bypassed by prompt content, but it is only as
strong as this validator. Enabling auth with a read-role user is a recorded
follow-up (KNOWN_ISSUES.md), not something this module can provide on its
own.

An ALLOWLIST is used deliberately, not a denylist: it fails safe as MongoDB
adds new aggregation stages, whereas a denylist silently admits them.
"""

# Read-only aggregation stages. Anything not listed here is rejected,
# including stages MongoDB may add in the future (research.md R6).
ALLOWED_STAGES = {
    "$match", "$project", "$addFields", "$set", "$group", "$sort", "$limit",
    "$skip", "$count", "$unwind", "$lookup", "$facet", "$sample",
    "$sortByCount", "$replaceRoot",
}

# Explicitly called out even though they're already absent from the
# allowlist above — documents intent for anyone reading this file, and these
# are exactly the stages research.md R6 named as the reason an allowlist
# (not a denylist) was chosen.
KNOWN_DANGEROUS_STAGES = {
    "$out", "$merge", "$function", "$accumulator", "$where", "$graphLookup",
}

# 035-chat-and-news-upgrade — news_articles added per US3. Per constitution
# Principle VI (amended v1.1.0), any collection admitted here MUST have a
# mirrored field-vocabulary contract test in both services (contracts/news-collection.md).
READABLE_COLLECTIONS = {"screener", "news_articles"}

DEFAULT_LIMIT = 50
HARD_LIMIT_CAP = 200
DEFAULT_MAX_TIME_MS = 5000


class QueryRejected(Exception):
    """A generated pipeline failed validation and must not be executed."""


def _stage_name(stage: dict) -> str:
    if not isinstance(stage, dict) or len(stage) != 1:
        raise QueryRejected(f"each pipeline stage must be a single-key object, got: {stage!r}")
    return next(iter(stage))


def _contains_text_operator(value) -> bool:
    """Recursively checks for a `$text` key anywhere in a stage's value —
    MongoDB rejects $text outside the pipeline's first $match stage at
    runtime, and FR-012 requires that become a plain-language decline
    (research.md R3), not a 500."""
    if isinstance(value, dict):
        return "$text" in value or any(_contains_text_operator(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_text_operator(v) for v in value)
    return False


def validate_pipeline(pipeline: list[dict], collection: str = "screener") -> list[dict]:
    """Validates a generated aggregation pipeline and returns a safe-to-run
    copy with a `$limit` guaranteed present and within HARD_LIMIT_CAP.

    Raises QueryRejected — never executes, never mutates the input — on any
    disallowed stage, malformed stage shape, non-list pipeline, or an
    explicit $limit above the hard cap. FR-015 requires callers to turn a
    QueryRejected into a plain-language "couldn't answer that safely"
    response, not a 500.
    """
    if collection not in READABLE_COLLECTIONS:
        raise QueryRejected(f"collection {collection!r} is not readable by chat")
    if not isinstance(pipeline, list):
        raise QueryRejected(f"pipeline must be a list of stages, got: {type(pipeline).__name__}")

    validated: list[dict] = []
    existing_limit: int | None = None

    for index, stage in enumerate(pipeline):
        name = _stage_name(stage)
        if name not in ALLOWED_STAGES:
            raise QueryRejected(f"stage {name!r} is not permitted for chat queries")
        if _contains_text_operator(stage[name]):
            if index != 0 or name != "$match":
                raise QueryRejected("$text may only appear in the pipeline's first $match stage")
        if name == "$limit":
            value = stage["$limit"]
            if not isinstance(value, int) or value > HARD_LIMIT_CAP:
                raise QueryRejected(
                    f"$limit {value!r} exceeds the maximum of {HARD_LIMIT_CAP}"
                )
            existing_limit = value
        validated.append(dict(stage))

    if existing_limit is None:
        validated.append({"$limit": DEFAULT_LIMIT})

    return validated

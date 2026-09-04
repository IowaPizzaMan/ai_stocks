"""Chat conversation persistence — history sidebar.
Spec: specs/035-chat-and-news-upgrade US5; contracts/chat-history-api.md; data-model.md §2.
"""
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.database import Database

import llm
from db import CHAT_CONVERSATIONS
from logging_config import get_logger

logger = get_logger(__name__)

TITLE_MAX_WORDS = 6


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _truncated_title(question: str) -> str:
    return " ".join(question.strip().split()[:TITLE_MAX_WORDS])


def _generate_title(question: str, answer: str, *, client=None) -> str:
    """One extra LLM call, made only once per conversation, after the first
    exchange (research.md R6). Falls back to a truncated first question on
    LLMError — a title is cosmetic metadata; persistence must never depend
    on the model succeeding."""
    try:
        title = llm.generate_text(
            prompt=(
                f"User asked: {question}\n\nAssistant answered: {answer}\n\n"
                f"Write a short title (at most {TITLE_MAX_WORDS} words) summarizing "
                "what this conversation is about. Reply with the title only — no "
                "quotes, no trailing punctuation."
            ),
            client=client,
            options={"temperature": 0.2},
        )
    except llm.LLMError as exc:
        logger.warning("conversation title generation failed, using fallback: %s", exc)
        return _truncated_title(question)

    words = title.strip().strip('"').split()
    return " ".join(words[:TITLE_MAX_WORDS]) if words else _truncated_title(question)


def _to_object_id(conversation_id: str) -> ObjectId | None:
    try:
        return ObjectId(conversation_id)
    except (InvalidId, TypeError):
        return None


def _message(role: str, content: str) -> dict:
    return {"role": role, "content": content, "timestamp": _utcnow()}


def create(question: str, answer: str, db: Database, *, client=None) -> dict:
    """Persists a new conversation's first exchange (FR-015). Returns the
    stored document, including its `_id`."""
    now = _utcnow()
    doc = {
        "title": _generate_title(question, answer, client=client),
        "created_at": now,
        "updated_at": now,
        "messages": [_message("user", question), _message("assistant", answer)],
    }
    result = db[CHAT_CONVERSATIONS].insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


def append(conversation_id: str, question: str, answer: str, db: Database) -> bool:
    """Appends one exchange to an existing conversation and bumps
    `updated_at` (FR-017's most-recent-first ordering) — never touches
    `title` (research.md R6: generated once, not regenerated per turn).
    Returns False (no write) for an unknown or malformed id."""
    oid = _to_object_id(conversation_id)
    if oid is None:
        return False
    result = db[CHAT_CONVERSATIONS].update_one(
        {"_id": oid},
        {
            "$push": {"messages": {"$each": [_message("user", question), _message("assistant", answer)]}},
            "$set": {"updated_at": _utcnow()},
        },
    )
    return result.matched_count > 0


def list_conversations(db: Database) -> list[dict]:
    """Sidebar listing (FR-017) — titles/dates only, most recent first."""
    docs = (
        db[CHAT_CONVERSATIONS]
        .find({}, {"title": 1, "created_at": 1, "updated_at": 1, "messages": 1})
        .sort("updated_at", -1)
    )
    return [
        {
            "id": str(doc["_id"]),
            "title": doc["title"],
            "created_at": doc["created_at"],
            "updated_at": doc["updated_at"],
            "message_count": len(doc.get("messages") or []),
        }
        for doc in docs
    ]


def get(conversation_id: str, db: Database) -> dict | None:
    """Full conversation for reopening (FR-018). None for an unknown or
    malformed id — a malformed id is indistinguishable from a deleted one
    from the caller's perspective."""
    oid = _to_object_id(conversation_id)
    if oid is None:
        return None
    doc = db[CHAT_CONVERSATIONS].find_one({"_id": oid})
    if doc is None:
        return None
    return {
        "id": str(doc["_id"]),
        "title": doc["title"],
        "created_at": doc["created_at"],
        "updated_at": doc["updated_at"],
        "messages": doc.get("messages") or [],
    }


def delete(conversation_id: str, db: Database) -> bool:
    """Hard delete (FR-019) — no soft-delete/audit trail in a single-user
    local app. False for an unknown or malformed id."""
    oid = _to_object_id(conversation_id)
    if oid is None:
        return False
    result = db[CHAT_CONVERSATIONS].delete_one({"_id": oid})
    return result.deleted_count > 0

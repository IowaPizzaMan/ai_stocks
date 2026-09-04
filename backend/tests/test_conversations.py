"""semantic/conversations.py — chat history persistence.
Spec: specs/035-chat-and-news-upgrade US5; contracts/chat-history-api.md; research.md R6.
"""
from semantic import conversations
from db import CHAT_CONVERSATIONS


class FakeTitleClient:
    def __init__(self, title: str):
        self.title = title
        self.calls = 0

    def chat(self, *, model, messages, format=None, think=None, keep_alive=None, options=None):
        self.calls += 1
        return {"message": {"content": self.title}}


class FailingClient:
    def chat(self, **kwargs):
        raise ConnectionError("ollama unreachable")


def test_create_uses_the_llm_generated_title(db, monkeypatch):
    fake = FakeTitleClient("NVDA recent news")
    doc = conversations.create("what's the latest on NVDA?", "Nvidia rose 3%.", db, client=fake)

    assert doc["title"] == "NVDA recent news"
    assert fake.calls == 1
    stored = db[CHAT_CONVERSATIONS].find_one({"_id": doc["_id"]})
    assert stored["title"] == "NVDA recent news"
    assert [m["role"] for m in stored["messages"]] == ["user", "assistant"]


def test_create_falls_back_to_truncated_question_on_llm_error(db):
    doc = conversations.create(
        "what stocks have improving financials this week and beyond", "Several do.",
        db, client=FailingClient(),
    )
    # <=6 words, no exception raised despite the title call failing.
    assert doc["title"] == "what stocks have improving financials this"


def test_create_falls_back_to_truncated_question_when_the_title_response_is_blank(db):
    doc = conversations.create("what stocks have improving financials", "Several do.", db, client=FakeTitleClient(""))
    assert doc["title"] == "what stocks have improving financials"


def test_append_pushes_both_messages_and_bumps_updated_at_without_changing_title(db):
    created = conversations.create("first question", "first answer", db, client=FakeTitleClient("Original Title"))
    conversation_id = str(created["_id"])
    before = conversations.get(conversation_id, db)

    ok = conversations.append(conversation_id, "second question", "second answer", db)

    assert ok is True
    after = conversations.get(conversation_id, db)
    assert after["title"] == "Original Title"
    assert len(after["messages"]) == 4
    assert after["messages"][2]["content"] == "second question"
    assert after["messages"][3]["content"] == "second answer"
    assert after["updated_at"] >= before["updated_at"]


def test_append_to_an_unknown_id_returns_false(db):
    assert conversations.append("000000000000000000000000", "q", "a", db) is False


def test_append_to_a_malformed_id_returns_false_not_raises(db):
    assert conversations.append("not-an-object-id", "q", "a", db) is False


def test_list_conversations_orders_by_updated_at_descending(db):
    first = conversations.create("q1", "a1", db, client=FakeTitleClient("First"))
    conversations.create("q2", "a2", db, client=FakeTitleClient("Second"))
    conversations.append(str(first["_id"]), "q1b", "a1b", db)  # bumps first to most-recent

    listing = conversations.list_conversations(db)

    assert [c["title"] for c in listing] == ["First", "Second"]
    assert listing[0]["message_count"] == 4
    assert listing[1]["message_count"] == 2


def test_list_conversations_empty_returns_empty_list(db):
    assert conversations.list_conversations(db) == []


def test_get_returns_full_messages(db):
    created = conversations.create("q", "a", db, client=FakeTitleClient("T"))
    result = conversations.get(str(created["_id"]), db)
    assert result["id"] == str(created["_id"])
    assert len(result["messages"]) == 2


def test_get_unknown_id_returns_none(db):
    assert conversations.get("000000000000000000000000", db) is None


def test_get_malformed_id_returns_none_not_raises(db):
    assert conversations.get("not-an-object-id", db) is None


def test_delete_removes_the_document(db):
    created = conversations.create("q", "a", db, client=FakeTitleClient("T"))
    ok = conversations.delete(str(created["_id"]), db)
    assert ok is True
    assert db[CHAT_CONVERSATIONS].find_one({"_id": created["_id"]}) is None


def test_delete_unknown_id_returns_false(db):
    assert conversations.delete("000000000000000000000000", db) is False


def test_delete_malformed_id_returns_false_not_raises(db):
    assert conversations.delete("not-an-object-id", db) is False

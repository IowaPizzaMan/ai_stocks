"""GET/DELETE /chat/conversations* — history sidebar CRUD.
Spec: specs/035-chat-and-news-upgrade US5; contracts/chat-history-api.md.
"""
from db import CHAT_CONVERSATIONS
from semantic import conversations


class FakeTitleClient:
    def chat(self, *, model, messages, format=None, think=None, keep_alive=None, options=None):
        return {"message": {"content": "A Title"}}


def _seed(db, title="A Title") -> str:
    doc = conversations.create("q", "a", db, client=FakeTitleClient())
    if title != "A Title":
        db[CHAT_CONVERSATIONS].update_one({"_id": doc["_id"]}, {"$set": {"title": title}})
    return str(doc["_id"])


def test_list_conversations_empty_returns_200_with_empty_list(client, db):
    r = client.get("/chat/conversations")
    assert r.status_code == 200
    assert r.json() == {"conversations": []}


def test_list_conversations_returns_title_and_dates(client, db):
    cid = _seed(db)
    r = client.get("/chat/conversations").json()
    assert len(r["conversations"]) == 1
    assert r["conversations"][0]["id"] == cid
    assert r["conversations"][0]["title"] == "A Title"
    assert r["conversations"][0]["message_count"] == 2


def test_get_conversation_returns_full_messages(client, db):
    cid = _seed(db)
    r = client.get(f"/chat/conversations/{cid}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == cid
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "user"


def test_get_unknown_conversation_is_404(client, db):
    r = client.get("/chat/conversations/000000000000000000000000")
    assert r.status_code == 404


def test_get_malformed_conversation_id_is_404_not_500(client, db):
    r = client.get("/chat/conversations/not-an-object-id")
    assert r.status_code == 404


def test_delete_conversation_returns_204(client, db):
    cid = _seed(db)
    r = client.delete(f"/chat/conversations/{cid}")
    assert r.status_code == 204
    assert db[CHAT_CONVERSATIONS].find_one({}) is None


def test_delete_unknown_conversation_is_404(client, db):
    r = client.delete("/chat/conversations/000000000000000000000000")
    assert r.status_code == 404


def test_deleting_twice_is_404_the_second_time(client, db):
    cid = _seed(db)
    first = client.delete(f"/chat/conversations/{cid}")
    second = client.delete(f"/chat/conversations/{cid}")
    assert first.status_code == 204
    assert second.status_code == 404

"""Chat API — ask a data-grounded question, get an answer.
Spec: specs/031-semantic-layer-chat; specs/035-chat-and-news-upgrade;
contracts/chat-api.md; contracts/chat-history-api.md.
"""
from fastapi import APIRouter, Depends, HTTPException, Response

from db import SCREENER
from deps import db_dependency
from semantic import chat as chat_engine
from semantic import conversations
from semantic.schema import SCREENER_SCHEMA

router = APIRouter(prefix="/chat", tags=["chat"])

MAX_QUESTION_CHARS = 2000


@router.get("/schema")
def get_schema(db=Depends(db_dependency)) -> dict:
    latest = db[SCREENER].find_one(sort=[("signals_as_of", -1)], projection={"signals_as_of": 1})
    return {
        "collection": SCREENER_SCHEMA["collection"],
        "fields": SCREENER_SCHEMA["fields"],
        "document_count": db[SCREENER].count_documents({}),
        "signals_as_of": latest["signals_as_of"] if latest else None,
    }


# 035-chat-and-news-upgrade US5 — registered before POST /chat's dynamic
# {conversation_id} paths below so "/conversations" itself is never treated
# as a path parameter.
@router.get("/conversations")
def list_conversations(db=Depends(db_dependency)) -> dict:
    return {"conversations": conversations.list_conversations(db)}


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, db=Depends(db_dependency)) -> dict:
    result = conversations.get(conversation_id, db)
    if result is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return result


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, db=Depends(db_dependency)) -> Response:
    if not conversations.delete(conversation_id, db):
        raise HTTPException(status_code=404, detail="conversation not found")
    return Response(status_code=204)


@router.post("")
def post_chat(body: dict, db=Depends(db_dependency)) -> dict:
    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="question is required")
    if len(question) > MAX_QUESTION_CHARS:
        raise HTTPException(status_code=422, detail=f"question exceeds {MAX_QUESTION_CHARS} characters")

    history = body.get("history") or []
    if not isinstance(history, list):
        raise HTTPException(status_code=422, detail="history must be a list")

    conversation_id = body.get("conversation_id")
    if conversation_id is not None:
        if not isinstance(conversation_id, str):
            raise HTTPException(status_code=422, detail="conversation_id must be a string")
        if conversations.get(conversation_id, db) is None:
            raise HTTPException(status_code=404, detail="conversation not found")

    return chat_engine.answer_question(question, history, db, conversation_id=conversation_id)

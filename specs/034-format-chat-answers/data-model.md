# Phase 1 Data Model: Format Chat Answers

No new or modified data entities. This feature is presentation-only (FR-008): it changes how
an already-existing field is *rendered* on the Chat page, not what is stored, sent, or
received.

## Existing entity touched (read-only)

**Assistant Answer** — `ChatResponse.answer: string`
([frontend/src/api/types.ts](../../frontend/src/api/types.ts)), produced by the backend chat
router. Unchanged shape and type. This feature interprets the existing string's content as
markdown at render time only; no field is added, removed, or retyped, and no request/response
schema changes on either the frontend `ChatResponse`/`ChatTurn` types or the backend chat
contract (`backend/routers/chat.py`, `specs/031-semantic-layer-chat/contracts/chat-api.md`).

## New (non-persisted) view-layer shape

`AnswerText`'s props are the only new "shape" introduced, and it is a UI component contract,
not a data entity — see [contracts/answer-text-component.md](./contracts/answer-text-component.md).

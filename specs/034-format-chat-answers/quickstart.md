# Quickstart: Format Chat Answers

Validates that assistant answers on the Chat page render as structured, styled markdown
instead of a raw text blob, per `spec.md`'s acceptance scenarios.

## Prerequisites

- `frontend/` deps installed with `react-markdown` and `remark-breaks` added (see
  `research.md` D1/D2).
- Dev stack running: `docker compose up` (or `cd frontend && npm run dev` against an already
  running backend), so the Chat page can reach `POST /chat` for a live answer. Automated
  checks below don't require the live LLM — they run against component tests with fixture
  answer strings.

## Automated validation

```bash
cd frontend
npm run typecheck
npm test -- Chat.test.tsx AnswerText.test.tsx
```

Expected: all tests pass, including (per `contracts/answer-text-component.md`'s FR table):

- multi-paragraph answer → separate paragraph blocks (FR-001)
- bulleted/numbered list, including a nested sub-list → distinct indented list items (FR-002)
- bold/italic/header/inline-code/blockquote markup → styled output, no literal `**`/`#`/`` ` ``/`>` characters visible (FR-003)
- an answer containing `<script>...</script>` text → shown as inert text, not executed (FR-004)
- plain single-sentence answer → renders unchanged from current behavior (FR-006)
- an answer with a single `\n` (no blank line) → visible line break, not collapsed (FR-009)
- an answer with a markdown link using a non-http(s) scheme → still rendered as a clickable `<a>` (FR-010)
- the same checks pass for every entry across a multi-exchange history, not just the latest (FR-007)

## Manual validation (Chat page, live LLM)

1. Open the Chat page.
2. Ask a question likely to produce a multi-point answer (e.g. a strategy or comparison
   question already used in `Chat.test.tsx` fixtures, such as "per my trading strategies,
   what should I buy this week and at what prices?").
3. Confirm the answer bubble shows separated paragraphs/list items, not one run-on block
   (US1).
4. Confirm any bolded terms (e.g. ticker symbols) show as bold text with no stray `*`
   characters (US2).
5. Resize the browser to a narrow (≈375px) width and confirm the answer wraps with no
   horizontal scrollbar (US3 / SC-004).
6. Ask a second, unrelated question in the same session and confirm both the first and
   second answers in the exchange history are formatted consistently (FR-007).

## Rollback check

Reverting to plain-text rendering only requires reverting the `AnswerText` call-site swap in
`Chat.tsx` (`git revert` on this feature's commit(s)) — no backend, API, or stored-data
migration is involved, since FR-008 guarantees no contract change.

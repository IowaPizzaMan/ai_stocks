# Implementation Plan: Format Chat Answers

**Branch**: `034-format-chat-answers` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/034-format-chat-answers/spec.md`

## Summary

The Chat page's assistant-answer bubble currently renders `ChatResponse.answer` as a single
raw string, so any markdown-style structure the LLM produced (paragraphs, lists, emphasis,
headers, links, code spans, blockquotes) shows up as an unbroken run of text with literal
formatting characters. This is a presentation-only change: replace the raw
`<p>{answer}</p>` in [Chat.tsx](../../frontend/src/pages/Chat.tsx) with a new
`AnswerText` component that parses the answer as markdown via `react-markdown` (+
`remark-breaks` for single-line-break preservation) and renders each element with
Tailwind classes matching the page's existing dark palette. No backend, API, or data
model changes (FR-008).

## Technical Context

**Language/Version**: TypeScript 5.6, React 18.3

**Primary Dependencies**: `react-markdown` (new), `remark-breaks` (new) — added to
`frontend/package.json`; no other frontend deps change

**Storage**: N/A — no persistence change; `ChatResponse.answer` is already a plain string

**Testing**: Vitest + React Testing Library (existing `frontend/src/pages/Chat.test.tsx`
pattern), new `frontend/src/components/chat/AnswerText.test.tsx`

**Target Platform**: Browser (Chat page), desktop and mobile viewport widths (FR-005)

**Project Type**: Web application (frontend-only change; `backend/` untouched)

**Performance Goals**: N/A — client-side markdown parsing of short chat answers, no
measurable perf budget beyond "no visible lag on submit," consistent with existing page

**Constraints**: MUST NOT execute embedded HTML/script (FR-004); MUST NOT change the chat
request/response contract (FR-008); MUST NOT require a new heavyweight dependency beyond a
markdown renderer + one plugin, per Principle V (simplicity)

**Scale/Scope**: Single component (`AnswerText`) plus one call-site swap in `Chat.tsx`;
answer text is typically a few sentences to a short multi-point list, not long documents

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First & Comprehensive Coverage** — `AnswerText` is a frontend component with
  user-facing rendering logic → requires Vitest + RTL coverage (new
  `AnswerText.test.tsx`), plus updated assertions in `Chat.test.tsx` where the raw-string
  match no longer applies. PASS (planned in Phase 1 / tasks).
- **II. Spec-Driven Development** — this plan traces to `specs/034-format-chat-answers/spec.md`
  (FR-001..FR-010). PASS.
- **III. Deterministic Core, LLM at the Edges** — no rule-engine skill touched; this is
  purely a rendering change of already-generated LLM text. N/A / PASS.
- **IV. Cache-Aware, Budget-Conscious Data Access** — no external data-source calls
  involved. N/A / PASS.
- **V. Simplicity & Local-First Scope** — adds exactly one rendering library
  (`react-markdown`) and one plugin (`remark-breaks`) rather than hand-rolling a markdown
  parser. A hand-rolled parser was considered and rejected (see research.md D1) because
  correctly and *safely* handling nested lists, links, and raw-HTML suppression (FR-004) is
  exactly the kind of parsing surface prone to XSS bugs if reimplemented ad hoc — using a
  vetted library is the simpler, safer choice here, not scope creep. No new infrastructure,
  no backend change. PASS.
- **VI. Consistency Across Layers** — no shared contract between `backend/` and
  `agent-runner/` is touched. N/A / PASS.

No violations requiring Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/034-format-chat-answers/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── answer-text-component.md
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── pages/
│   │   ├── Chat.tsx              # MODIFIED: swap raw <p>{answer}</p> for <AnswerText>
│   │   └── Chat.test.tsx         # MODIFIED: update assertions affected by markdown rendering
│   └── components/
│       └── chat/                 # NEW directory (follows existing per-page component dirs,
│           │                     #   e.g. components/congress/, components/earnings/)
│           ├── AnswerText.tsx        # NEW: react-markdown wrapper + styled element map
│           └── AnswerText.test.tsx   # NEW: RTL coverage for FR-001..FR-010 + edge cases
└── package.json                  # MODIFIED: add react-markdown, remark-breaks

backend/        # untouched (FR-008)
agent-runner/   # untouched
```

**Structure Decision**: Web application, Option 2 layout already in use by this repo
(`backend/` + `frontend/`). This feature only touches `frontend/`. A new
`components/chat/` directory holds the single new component, matching the existing
convention of one component subdirectory per page/feature area (`components/congress/`,
`components/earnings/`, `components/stock/`, …) rather than adding it to the already-large
`Chat.tsx` inline or to the unrelated `components/stock/` directory.

## Complexity Tracking

*No Constitution Check violations — table intentionally omitted.*

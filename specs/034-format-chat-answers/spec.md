# Feature Specification: Format Chat Answers

**Feature Branch**: `034-format-chat-answers`

**Created**: 2026-08-23

**Status**: Draft

**Input**: User description: "I would like to format the output from the LLM on the chat page. I need this to read nicely."

## Clarifications

### Session 2026-08-23

- Q: Beyond paragraphs, lists, and bold/italic, should any other common markdown elements (headers, links, inline code spans, blockquotes) be rendered as styled/functional output, or treated as plain literal text? → A: Also style headers, links, inline code spans, and blockquotes as functional/styled output.
- Q: When the assistant's answer has a single line break (not a blank line) between two lines of text, should that render as a visible line break, or be treated as a soft wrap (joined with a space, standard CommonMark behavior)? → A: Preserve every single line break as a visible line break.
- Q: Do list items need to support nested sub-lists, or is single-level list rendering sufficient? → A: Support nested sub-lists, indented beneath their parent item.
- Q: Now that links render as clickable, should link targets be restricted to safe URL schemes (http/https only), or are all schemes allowed? → A: Allow any scheme the assistant produces — no scheme restriction or validation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Scan a multi-point answer at a glance (Priority: P1)

A user asks a question on the Chat page that the assistant answers with several distinct
points (e.g. a comparison across a handful of matching stocks, or a multi-part explanation).
Today that answer arrives as one unbroken block of text, so paragraph breaks and any list
structure the assistant produced are squashed together and hard to scan. The user wants to
read the answer as clearly delineated paragraphs and list items, the way the assistant
intended it.

**Why this priority**: This is the core complaint — "read nicely" — and the answer text is
the part of every chat response the user reads on every single question. Nothing else in the
feature matters if this isn't fixed.

**Independent Test**: Ask a question that produces a multi-sentence, multi-point answer (e.g.
one comparing several tickers) and confirm the response renders as separated paragraphs/list
items rather than one continuous line of text.

**Acceptance Scenarios**:

1. **Given** an assistant answer containing multiple paragraphs, **When** the response is
   displayed, **Then** each paragraph appears as a visually separate block rather than being
   run together.
2. **Given** an assistant answer containing a bulleted or numbered list, **When** the response
   is displayed, **Then** each item appears as a distinct list entry rather than inline text.

---

### User Story 2 - Spot key details within the answer (Priority: P2)

While reading an answer, the user wants emphasized details — such as bolded ticker symbols or
standout metrics the assistant chose to call out — to be visually distinguishable from the
surrounding prose, instead of appearing as raw emphasis characters (e.g. literal asterisks)
mixed into the sentence.

**Why this priority**: Improves scannability further once the base structure (US1) is fixed,
but the answer is still usable without it.

**Independent Test**: Ask a question whose answer includes emphasized terms and confirm those
terms render as visually styled text with no stray formatting characters visible.

**Acceptance Scenarios**:

1. **Given** an assistant answer containing emphasized text, **When** the response is
   displayed, **Then** the emphasized text is visually distinguished (e.g. bold/italic
   styling) and no literal emphasis characters are shown.

---

### User Story 3 - Answer stays readable on any device (Priority: P3)

A user reading the chat on a narrow (mobile-width) window wants a long or densely formatted
answer to remain fully readable — wrapping normally — rather than overflowing the screen or
forcing horizontal scrolling.

**Why this priority**: A layout regression here would undercut US1/US2's readability gains for
part of the audience, but the base desktop experience is the primary use case.

**Independent Test**: Resize the Chat page to a narrow viewport, ask a question with a long
answer, and confirm the text wraps within the visible width with no horizontal scrollbar.

**Acceptance Scenarios**:

1. **Given** a long assistant answer, **When** viewed at a narrow viewport width, **Then** all
   text wraps within the container and no horizontal scrolling is required.

### Edge Cases

- What happens when the answer contains no formatting at all (a single plain sentence)? It
  must still render exactly as clearly as before — no regression for the common case.
- What happens when the answer contains malformed or partial formatting markers (e.g. an
  unclosed emphasis marker)? The answer must still render fully and readably; it must not
  break the page or hide any of the answer's content.
- What happens when the answer contains characters that resemble HTML or script markup? They
  must never be executed or rendered as live markup — only shown as inert text.
- What happens when the answer is very short (e.g. "No stocks matched that criteria.")? It
  renders as today, unaffected by the new formatting.
- What happens across multiple exchanges in one conversation? Each answer in the exchange
  history is formatted consistently, not just the most recent one.
- What happens when the answer contains a markdown link with a non-http(s) scheme (e.g.
  `javascript:`, `data:`)? Per clarification, it still renders as a clickable link with no
  scheme restriction — this applies only to link targets produced via markdown link syntax,
  and is distinct from FR-004's prohibition on rendering raw embedded HTML/script content that
  is not part of recognized markdown syntax.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Chat page MUST render paragraph breaks present in an assistant answer as
  visually distinct paragraphs rather than collapsing them into a single run of text.
- **FR-002**: The Chat page MUST render bulleted and numbered list structures present in an
  assistant answer as distinct, visually indented list items, including nested sub-lists
  indented beneath their parent item.
- **FR-003**: The Chat page MUST render emphasized text (bold/italic), headers, inline code
  spans, and blockquotes present in an assistant answer as styled text, without showing the
  raw markup characters to the user.
- **FR-004**: The Chat page MUST NOT execute or render any embedded HTML/script content from
  an assistant answer as live markup — all answer content other than recognized markdown
  formatting (paragraphs, lists, emphasis, headers, links, inline code, blockquotes) is
  displayed as inert, safe text.
- **FR-005**: The Chat page MUST keep answer text fully readable and free of horizontal
  overflow at both desktop and mobile viewport widths.
- **FR-006**: An assistant answer with no special formatting MUST continue to render as a
  plain, readable paragraph, matching today's behavior.
- **FR-007**: The new formatting MUST apply to every answer shown in the exchange history, not
  only the most recently received one.
- **FR-008**: This feature changes only how the existing answer text is displayed; it MUST NOT
  require any change to the chat request/response contract.
- **FR-009**: The Chat page MUST render a single line break within the assistant's answer (a
  newline not separated by a blank line) as a visible line break, rather than collapsing it
  into a continuous run of text.
- **FR-010**: The Chat page MUST render markdown links present in an assistant answer as
  clickable hyperlinks; the link's URL scheme MUST NOT be restricted or validated before it is
  rendered as clickable.

### Key Entities

- **Assistant Answer**: The free-form natural-language text returned per chat exchange, shown
  in the Chat page's response list. This feature governs only how this text is presented, not
  how it is produced.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can distinguish every paragraph and list item in a multi-point assistant
  answer at a glance, without needing to mentally re-parse a single unbroken block of text.
- **SC-002**: Zero assistant answers display raw formatting syntax (literal asterisks, dashes,
  hash symbols, backticks, list markers, or link brackets/parentheses) as visible characters
  when that syntax was used to convey structure.
- **SC-003**: 100% of assistant answers, regardless of content, render fully and safely — no
  broken layout, no executed markup, no missing text.
- **SC-004**: Long assistant answers remain fully readable at a 375px-wide viewport with no
  horizontal scrolling.

## Assumptions

- The assistant's answer text may contain lightweight markdown-style formatting: paragraph
  breaks, single line breaks, bullet/numbered lists (including nested sub-lists), bold/italic
  emphasis, headers, links, inline code spans, and blockquotes. Support for these structures is
  sufficient to satisfy "read nicely" — advanced formatting such as tables, fenced code blocks,
  or images remains out of scope for this feature.
- This feature is scoped to the free-form answer text bubble specifically. The already
  structured parts of a chat response (strategy picks, criteria list, generated query, status
  notices) are out of scope — they are already rendered with dedicated layouts.
- No changes to the chat backend or API contract are required; this is a presentation-only
  change on the Chat page.

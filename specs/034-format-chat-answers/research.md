# Phase 0 Research: Format Chat Answers

## D1: Markdown rendering approach

**Decision**: Use `react-markdown` (remark/CommonMark pipeline, React 18-compatible) as the
renderer, with `remark-breaks` added so a single newline renders as a visible line break
(FR-009) instead of standard CommonMark's soft-wrap-to-space behavior.

**Rationale**:
- The repo already has a precedent for "make LLM prose read nicely" —
  [`frontend/src/lib/prose.ts`](../../frontend/src/lib/prose.ts) +
  [`frontend/src/components/stock/FormattedProse.tsx`](../../frontend/src/components/stock/FormattedProse.tsx)
  (specs/021-stock-page-redesign). It was evaluated first and rejected for this feature:
  it's a heuristic sentence-splitter/keyword-highlighter, not a markdown parser — it has no
  concept of `- item` / `1. item` lists (nested or flat), `[text](url)` links, `` `code` ``
  spans, `> quote` blockquotes, or `#`/`##` headers, all of which FR-002/FR-003/FR-010
  require. Extending it to cover those would mean writing a bespoke markdown parser by hand.
- Hand-rolling markdown parsing (even a subset) is exactly the kind of surface where a
  homegrown implementation risks XSS bugs (FR-004: never execute embedded HTML/script) or
  malformed-input crashes (edge case: unclosed emphasis markers must still render safely).
  `react-markdown` never uses `dangerouslySetInnerHTML` and treats raw HTML found in the
  source as inert plain text by default (no `rehype-raw` plugin is added) — this satisfies
  FR-004 for free, with no custom sanitization code to get wrong.
- It renders real React elements (not an HTML string), so Tailwind styling and RTL testing
  work the same way as any other component.

**Alternatives considered**:
- **Extend `formatProse`/`FormattedProse`** — rejected: wrong tool (heuristic prose
  splitter, not a markdown-syntax parser); see above.
- **`marked` / `markdown-it` + `dangerouslySetInnerHTML`** — rejected: would require adding
  a separate sanitizer (e.g. DOMPurify) to safely satisfy FR-004, i.e. two new dependencies
  and a manual sanitization step instead of one library that's safe by construction.
  `react-markdown` is the smaller, safer footprint.
- **Regex-based line/asterisk formatter (extend current raw string approach)** — rejected:
  cannot correctly handle nested lists (explicit clarification requirement) or links without
  effectively becoming a hand-written parser; same XSS/robustness risk as above.

## D2: Line-break semantics (FR-009)

**Decision**: `remark-breaks` plugin, which turns every single `\n` in the source into a
hard line break (`<br>`), matching the clarified requirement ("preserve every single line
break as a visible line break") rather than default CommonMark behavior (a single newline is
a soft wrap, joined with a space).

**Rationale**: This is a deliberate deviation from standard CommonMark that the spec's
clarification session explicitly chose. `remark-breaks` is the standard, minimal remark
plugin for exactly this behavior — no custom preprocessing of the answer string needed.

**Alternatives considered**: Pre-processing the answer string to convert `\n` → `\n\n`
before handing it to `react-markdown` — rejected: would also collapse intentional blank-line
paragraph breaks' spacing semantics and double up spacing inside list items; the plugin
handles the AST-level distinction (line break vs. paragraph break) correctly instead.

## D3: Element styling

**Decision**: Style markdown output via `react-markdown`'s `components` prop, mapping each
element (`p`, `ul`, `ol`, `li`, `strong`, `em`, `h1`-`h6`, `a`, `code`, `blockquote`) to a
small JSX wrapper using Tailwind utility classes drawn from the palette already used
elsewhere on the Chat page (`text-zinc-100`/`text-zinc-300`/`text-zinc-500`, `text-sky-500`
for links, `border-zinc-800` for blockquote rule). No new design-system dependency.

**Rationale**: The project has no `@tailwindcss/typography` (`prose` classes) dependency
today, and Chat.tsx's existing hand-styled elements (criteria list, strategy-picks list) all
use bespoke Tailwind utility classes rather than the typography plugin. Matching that
existing convention keeps one styling approach across the page instead of mixing a
prose-plugin look with hand-styled sections. `components` overrides are `react-markdown`'s
documented mechanism for this and require no extra dependency.

**Alternatives considered**: Add `@tailwindcss/typography` and wrap output in a `.prose`
div — rejected: introduces a second, differently-themed styling system on a page that
already hand-styles every other element; would need per-project dark-theme tuning (`prose
prose-invert`) to match anyway, at which point the `components` override is no more work and
stays consistent with the rest of the codebase.

## D4: Nested list indentation (clarification requirement)

**Decision**: Apply consistent `pl-*` (left padding) Tailwind classes to every `ul`/`ol`
override. Because nested lists are just additional `<ul>`/`<ol>` elements nested inside an
`<li>` in the rendered DOM, per-level padding stacks automatically — no manual depth
tracking needed.

**Rationale**: `react-markdown`'s default AST-to-DOM mapping already nests sub-lists inside
their parent `<li>` per CommonMark's list-nesting rules; only visual indentation needs to be
added via CSS, which composes naturally with DOM nesting.

## D5: Link target scheme (FR-010) and behavior

**Decision**: Render links exactly as `react-markdown` produces them — `href` taken directly
from the markdown source with no scheme allowlist/validation (per the clarification: "no
scheme restriction or validation"). Open links in a new tab (`target="_blank" rel="noopener
noreferrer"`) since the Chat page holds conversation state only in memory
(`frontend/src/pages/Chat.tsx` — stateless, no persistence per FR-004 of
specs/031-semantic-layer-chat); navigating away in the same tab would silently lose the
conversation.

**Rationale**: `rel="noopener noreferrer"` is a standard, no-cost hardening for
`target="_blank"` links (prevents the opened page from getting a `window.opener` handle) and
does not conflict with "no scheme restriction" (it doesn't block or validate the scheme,
just isolates the new tab).

**Alternatives considered**: Same-tab navigation (default anchor behavior) — rejected: would
silently discard the in-memory chat history the moment a user clicks a link the assistant
produced, a worse regression than the feature is meant to fix.

## D6: Testing impact

**Decision**: Existing `Chat.test.tsx` assertions that call `screen.getByText(fullAnswerString)`
continue to work unmodified for the fixture answers already in that file, because those
fixture strings are single-sentence/single-paragraph plain text with no markdown syntax —
`react-markdown` renders them as one `<p>` element, so the full string still matches one DOM
node. New tests (in `AnswerText.test.tsx`, and any new `Chat.test.tsx` cases) covering
multi-paragraph, list, and emphasis answers must query by substring/role instead of a full
raw-string match, since those answers span multiple elements once rendered.

**Rationale**: Confirmed by reading `frontend/src/pages/Chat.test.tsx` — all current
`flagshipResponse`/`strategyPicksResponse` `answer` fixtures are single-line strings.
Documented here so `/speckit-tasks` doesn't need to re-derive it.

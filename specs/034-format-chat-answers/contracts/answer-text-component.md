# Component Contract: `AnswerText`

This feature has no external API surface (FR-008: no chat request/response contract change).
The only interface it introduces is a new internal React component. Documented here as the
"contract" per the plan template, for `/speckit-tasks` and any future caller.

**File**: `frontend/src/components/chat/AnswerText.tsx`

## Props

```ts
interface AnswerTextProps {
  /** Raw assistant answer text, e.g. ChatResponse.answer. May contain markdown-style
   *  formatting (paragraphs, single line breaks, lists incl. nested, bold/italic, headers,
   *  links, inline code, blockquotes) or be plain text with none of the above. */
  text: string;
}

export default function AnswerText(props: AnswerTextProps): JSX.Element;
```

## Behavior contract (traces to spec.md Functional Requirements)

| Input | Output | FR |
|---|---|---|
| Text with a blank line between two lines | Two separate `<p>` blocks | FR-001 |
| `- item` / `1. item` lines, including indented nested items | `<ul>`/`<ol>` with nested `<ul>`/`<ol>` inside the parent `<li>` | FR-002 |
| `**bold**`, `*italic*`, `# Header`, `` `code` ``, `> quote` | Styled `<strong>`/`<em>`/`<h1..h6>`/`<code>`/`<blockquote>`, no literal markup characters shown | FR-003 |
| Embedded `<script>` / raw HTML tags in the text | Rendered as inert literal text, never executed | FR-004 |
| Long unbroken content at 375px viewport width | Wraps within the container, no horizontal scroll | FR-005 |
| Plain text with no formatting | Renders as a single plain paragraph, unchanged from prior behavior | FR-006 |
| Single `\n` (no blank line) | Visible line break within the same block | FR-009 |
| `[text](url)` for any URL scheme | Clickable `<a href="url">`, no scheme allowlist/validation applied | FR-010 |

## Caller contract

`frontend/src/pages/Chat.tsx` replaces:

```tsx
<p className="text-sm text-zinc-100">{exchange.response.answer}</p>
```

with:

```tsx
<AnswerText text={exchange.response.answer} />
```

for every exchange in `exchanges` (FR-007 — applies uniformly across the whole exchange
history, not just the newest entry).

## Non-contract (explicitly out of scope)

- Fenced code blocks, tables, and images are not part of this contract (spec Assumptions:
  out of scope for this feature).
- No new props beyond `text`; no imperative ref API; no callback props — the component is a
  pure function of its input text.

# Research: Remove Stock Page Horizontal Overflow

No `NEEDS CLARIFICATION` markers remain in the Technical Context — this feature is a
small, localized frontend layout fix within the existing stack, so research here focuses
on confirming root cause and choosing among implementation/testing approaches rather than
resolving stack unknowns.

## 1. Root cause of the horizontal overflow

**Decision**: The overflow is caused by two compounding issues in the shared app shell
(`frontend/src/App.tsx`, `frontend/src/components/layout/Sidebar.tsx`):
1. `<main className="flex-1 p-6">` (`App.tsx:21`) is a flex item with no `min-w-0`. Flex
   items default to `min-width: auto`, which resolves to their content's intrinsic width —
   so `<main>` can never shrink below the widest thing rendered inside it, no matter how
   narrow the viewport is.
2. `<aside className="w-56 shrink-0 ...">` (`Sidebar.tsx:77`) is a fixed 224px-wide,
   non-shrinking flex sibling, so it always claims 224px regardless of viewport width.

Together, once viewport width drops below (sidebar width + main's intrinsic content
width), the flex row (`<div className="flex">` in `App.tsx:19`) is forced wider than the
viewport, producing page-level horizontal scroll. This matches the existing entry in
`KNOWN_ISSUES.md` ("App shell causes horizontal page scroll at phone widths (~390px)").

**Rationale**: Confirmed by reading the current source of `App.tsx` and `Sidebar.tsx`
directly; the mechanism (missing `min-w-0` on a flex child) is a well-known CSS flexbox
behavior, not project-specific guesswork.

**Alternatives considered**:
- *Do nothing at the `<main>` level, fix only within `StockDetail.tsx`*: rejected — the
  stock page's own content already wraps correctly (header uses `flex-wrap`, `TabBar` uses
  `flex-wrap`); the forcing width comes from the shell, not the page, so a page-only fix
  can't work.
- *`overflow-x: auto` / `overflow-x: hidden` on `<main>` or the outer shell*: rejected —
  this would hide the symptom (or silently clip content) instead of allowing the intended
  responsive reflow, and conflicts with FR-001 ("no page-level horizontal scrolling"),
  which requires content to fit, not scroll or be clipped.

## 2. Sidebar behavior at narrow widths

**Decision**: Hide the Watchlist `Sidebar` below a responsive breakpoint (Tailwind
`md:` / 768px) using a display utility (`hidden md:block`) rather than building a
collapsible drawer or hamburger nav.

**Rationale**: The spec's Assumptions section explicitly defers exact sidebar adaptation
to planning and says no new nav pattern is required unless necessary to eliminate
overflow. Hiding below `md` is the simplest change that satisfies FR-001–003 without new
components, consistent with Constitution Principle V (no infrastructure/UI pattern added
ahead of a demonstrated need). The watchlist remains fully available at tablet/desktop
widths (≥768px), which is where it's actually usable as a persistent side panel; at phone
widths a persistent 224px-wide list of tickers wasn't usable UX regardless of the overflow
bug.

**Alternatives considered**:
- *Collapsible drawer/hamburger menu*: rejected for this feature — meaningfully larger
  scope (new component, open/close state, focus management, its own tests) for a feature
  whose acceptance criteria only require no page-level horizontal scroll; can be a future
  enhancement if mobile watchlist access is separately requested.
- *Let the sidebar shrink proportionally (e.g. percentage width instead of `w-56`)*:
  rejected — the ticker rows and remove-icon buttons inside `WatchlistRow` have their own
  minimum legible width; shrinking the container without a matching internal redesign would
  just move the overflow/clipping problem inside the sidebar instead of removing it.

## 3. Stock page header text wrapping

**Decision**: Apply the codebase's existing `min-w-0` + `truncate` idiom to the ticker
symbol / company name row in `StockDetail.tsx`'s header (`h1` + adjacent `record?.name`
span), matching the same pattern already used in `Stocks.tsx:73`,
`InstitutionalFlowCard.tsx:41-43`, and `EconomicCalendarPanel.tsx:28-47`.

**Rationale**: The header row is already `flex flex-wrap items-center justify-between
gap-3` (`StockDetail.tsx:77`), which handles wrapping between elements, but a single very
long, unbroken company name inside one flex child can still force that child (and thus the
row) wider than available space unless that child has `min-w-0` to permit shrinking, paired
with `truncate` to keep the overflow from spilling. Using the exact pattern already proven
elsewhere in this codebase keeps the fix idiomatic rather than introducing a new approach.

**Alternatives considered**:
- *`break-words` instead of `truncate`*: considered for the company-name span (wrapping to
  a second line instead of truncating with an ellipsis) — left as an implementation-time
  choice between `truncate` and `break-words` depending on visual review; both satisfy
  FR-005, since either prevents the name from forcing horizontal overflow. `truncate` is
  favored as the default since it's the dominant existing pattern in this codebase for
  single-line name/label fields.

## 4. Verifying "no horizontal overflow" given the frontend test stack

**Decision**: Automated Vitest/RTL tests assert the structural fix is present (specific
Tailwind classes on specific elements) as a regression guard; actual visual/overflow
verification is done manually against the Vite dev server at representative widths
(320px, 390px, 768px, 1920px), documented as a runnable checklist in `quickstart.md`.

**Rationale**: jsdom (the test environment used by this frontend's Vitest config) does not
implement CSS layout or paint — it cannot compute element widths, flex-shrink behavior, or
scrollbar presence. There is no Playwright/browser-based e2e tool in `frontend/`
currently (`package.json` has no such dependency), and adding one solely for this fix would
be new test infrastructure disproportionate to a CSS layout change (Constitution
Principle V). This mirrors this session's own operating guidance: "for UI or frontend
changes... use the feature in a browser before reporting the task as complete... if you
can't test the UI [via automated tests], say so explicitly."

**Alternatives considered**:
- *Add Playwright for real-browser overflow assertions*: rejected as disproportionate new
  infrastructure for a single layout fix; revisit only if a future feature demonstrates a
  recurring need for real-browser layout testing.
- *Skip automated tests entirely, rely only on manual verification*: rejected — Constitution
  Principle I requires test coverage for user-facing logic; structural class-presence tests
  at least catch an accidental revert of the fix (e.g., someone removing `min-w-0` from
  `<main>` later), even though they can't independently prove zero overflow.

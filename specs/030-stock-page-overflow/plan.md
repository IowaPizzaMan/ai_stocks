# Implementation Plan: Remove Stock Page Horizontal Overflow

**Branch**: `030-stock-page-overflow` | **Date**: 2026-08-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/030-stock-page-overflow/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

The stock detail page inherits a page-level horizontal scroll bug from the shared app
shell: `<main>` in `App.tsx` is a flex child with no `min-w-0`, so it can't shrink below
its content's intrinsic width, and the fixed-width (`w-56 shrink-0`) Watchlist `Sidebar`
never collapses — together they force the whole page wider than the viewport at narrow
widths (documented in `KNOWN_ISSUES.md`). The fix is a small, localized CSS/layout change
using patterns already established elsewhere in this codebase (`min-w-0` on flex
containers paired with `truncate` on the text that would otherwise force width, e.g.
`Stocks.tsx:73`, `InstitutionalFlowCard.tsx:41`): add `min-w-0` to `<main>`, hide the
Sidebar below a responsive breakpoint instead of building new mobile nav, and make the
stock page's ticker/company-name header text wrap or truncate rather than force width.
No new dependencies, no new routes, no data model changes.

## Technical Context

**Language/Version**: TypeScript 5.6, React 18.3 (frontend only; no backend/agent-runner changes)

**Primary Dependencies**: Tailwind CSS v4 (existing), React Router v6 (existing) — no new dependencies introduced

**Storage**: N/A — pure UI/layout change, no data changes

**Testing**: Vitest + React Testing Library (existing frontend convention). jsdom has no real
layout/paint engine, so RTL cannot directly assert "no horizontal scrollbar exists" —
tests instead assert the structural fix is present (e.g., `min-w-0` on the shell's
`<main>`, the Sidebar's responsive-hide class, `truncate`/wrap classes on the header name).
Actual cross-width overflow verification is done manually against the Vite dev server at
320px/390px/768px/1920px, per this session's UI-verification guidance — see
`quickstart.md`.

**Target Platform**: Web browser, existing `frontend` Docker Compose service

**Project Type**: Web application (existing `backend/` + `frontend/` split) — this feature
touches `frontend/` only

**Performance Goals**: N/A — layout-only change, no new runtime work

**Constraints**: No page-level horizontal scroll from 320px to 1920px viewport width
(FR-001–003); must not regress other pages sharing the same app shell (FR-006); no new
navigation pattern (e.g. hamburger/drawer) unless required to eliminate overflow (spec
Assumptions)

**Scale/Scope**: Three existing files (`App.tsx`, `Sidebar.tsx`, `StockDetail.tsx`) plus
their existing test files; no new components, no new pages

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Test-First & Comprehensive Coverage** — Applies. This is a frontend layout change,
  so the relevant bar is Vitest + RTL coverage of "user-facing logic," which for a CSS fix
  means structural assertions (right classes present on the right elements) rather than
  pixel-level layout — jsdom doesn't compute real layout, so that's the ceiling of what an
  automated test can prove here. Real overflow verification happens manually in-browser
  (documented in `quickstart.md`) before this is considered done. PASS, with this
  documented limitation.
- **II. Spec-Driven Development** — Satisfied by this Spec Kit workflow itself
  (`specs/030-stock-page-overflow/`).
- **III. Deterministic Core, LLM at the Edges** — N/A, no skills or LLM involvement.
- **IV. Cache-Aware, Budget-Conscious Data Access** — N/A, no external data calls.
- **V. Simplicity & Local-First Scope** — PASS. Fix uses existing Tailwind utilities and an
  existing codebase idiom (`min-w-0` + `truncate`, already used in `Stocks.tsx`,
  `InstitutionalFlowCard.tsx`, `EconomicCalendarPanel.tsx`); no new dependencies, no new
  infrastructure, no drawer/hamburger nav component built ahead of need.
- **VI. Consistency Across Layers** — N/A, frontend-only, no backend/agent-runner shared
  concepts touched.
- **Technology Stack Constraints** — No deviation; stays within the existing
  React 18 + Vite + Tailwind v4 + React Router v6 stack.

No violations. Complexity Tracking table not needed.

**Post-Phase 1 re-check**: Design artifacts (`research.md`, `data-model.md`,
`quickstart.md`) confirm the fix stays within the three files identified above, uses only
existing dependencies, and adds no new entities or interfaces. No new violations
introduced — gates still PASS.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── App.tsx                            # shell: add min-w-0 to <main>
│   ├── App.test.tsx                       # existing shell test, extend for overflow-relevant structure
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx                # hide below responsive breakpoint instead of forcing width
│   │   │   └── Sidebar.test.tsx
│   │   └── shared/
│   │       └── TabBar.tsx                 # already wraps (flex-wrap) — verify only, no change expected
│   └── pages/
│       ├── StockDetail.tsx                # header ticker/company-name: min-w-0 + truncate/wrap
│       └── StockDetail.test.tsx
```

**Structure Decision**: Existing Option 2 (web application: `backend/` + `frontend/`)
structure, already in place. This feature is entirely within `frontend/src/` and touches
no backend code. Changes are localized to the three files above plus their existing test
files — no new files, components, or directories are introduced.

## Complexity Tracking

> No violations — this section is intentionally empty.

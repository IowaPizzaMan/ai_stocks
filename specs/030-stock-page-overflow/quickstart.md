# Quickstart: Verify Stock Page Horizontal Overflow Is Gone

No API/interface contracts apply to this feature (see [research.md](research.md) §4) — it's
a frontend-only layout fix, so validation is a mix of automated structural tests and manual
in-browser resizing.

## Prerequisites

- `frontend/` dependencies installed (`npm install` inside `frontend/`, if not already done)
- A ticker that exists in the local dataset, or any valid `/stock/:ticker` route (the page
  renders its chart/tab shell even without a completed analysis — see `StockDetail.tsx`)

## 1. Run the automated regression tests

```bash
cd frontend
npm run test
```

Expect the existing suite to pass, plus the new/updated assertions from this feature:

- `App.test.tsx` — `<main>` carries `min-w-0` alongside `flex-1`.
- `Sidebar.test.tsx` — the `<aside>` carries the responsive hide class (`hidden md:block`
  or equivalent) in addition to `w-56 shrink-0`.
- `StockDetail.test.tsx` — the ticker/company-name header elements carry `min-w-0` +
  `truncate` (or `break-words`).

These are structural/class-presence assertions only — see the limitation noted in
`research.md` §4 (jsdom does not compute real layout, so it cannot itself prove zero
horizontal scroll).

## 2. Manually verify no horizontal scroll in-browser

```bash
cd frontend
npm run dev
```

Open the app in a browser, navigate to any `/stock/:ticker` page, open dev tools'
responsive/device toolbar, and check each width below for a horizontal scrollbar or any
content clipped past the right edge:

| Width  | What it represents                          | Expected result |
|--------|----------------------------------------------|------------------|
| 320px  | Smallest common phone width                   | No horizontal scrollbar (SC-002) |
| 390px  | Common modern phone width                     | No horizontal scrollbar; all header controls reachable (SC-001) |
| 768px  | Tablet / sidebar breakpoint boundary          | Sidebar reappears without reintroducing overflow |
| 1920px | Wide desktop                                  | Unchanged centered/max-width layout (no regression) |

Also drag the browser window slowly from wide to 320px (not just jumping between preset
widths) to confirm the layout reflows continuously with no horizontal scrollbar appearing
at any intermediate width (SC-003, User Story 2).

## 3. Spot-check edge cases

- Open a ticker with an unusually long company name and confirm the header wraps/truncates
  instead of widening the page.
- Open a tab with a wide data table (e.g. Institutional) and confirm it still scrolls
  *within its own container* — that's intentional, existing behavior (FR-004, SC-004), not
  something this fix should remove.
- Visit a non-stock page that shares the app shell (e.g. the main feed `/`) at 390px and
  confirm it still has no horizontal scrollbar either (FR-006, SC-005) — the shell fix is
  shared, so this is a quick regression check, not new scope.

## Done when

- Automated tests in step 1 pass.
- No horizontal scrollbar appears at any width checked in step 2.
- Edge cases in step 3 all behave as expected.

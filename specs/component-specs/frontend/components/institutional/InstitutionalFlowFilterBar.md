# frontend/src/components/institutional/InstitutionalFlowFilterBar.tsx

## Purpose
Sticky filter bar above the Institutional Flow feed. Controls which events are shown, plus a manual "Scan Now" trigger — consistent with the app's no-polling, manual-pull data model (`SPEC.md` → "UI Data Refresh: Manual Pull").

## Props
```typescript
interface InstitutionalFlowFilterBarProps {
  onChange: (filters: InstitutionalFlowFilters) => void
  activeFilters: InstitutionalFlowFilters
}
```

## Filter Controls
1. **Action** — pill toggle group: All | New Position | Add | Trim | Exit
2. **Fund** — text input, debounced, matches fund name (case-insensitive substring)
3. **Ticker** — text input, jumps to a single ticker's flow history
4. **Min notability** — slider, 0–100, defaults to 0 (filters out passive/index noise when raised)
5. **Clear** — "Clear filters" text button, only visible when a filter is active
6. **Scan Now** — button on the right side of the bar, calls `POST /institutional/scan`, then shows a toast: "Scan requested — refresh in a minute to see new activity"

## URL Sync
Same pattern as `FilterBar.md` — all filters stored as URL search params via `useSearchParams`.

## Styling
- Same visual language as `FilterBar.md`: pill toggles, `sticky top-14 z-40 bg-slate-950 border-b border-slate-800`
- `Scan Now` button: `bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg px-3 py-1.5`, shows a spinner while the request is in flight

## Dependencies
- `react-router-dom` (useSearchParams)
- `ACTION_FILTERS` from constants
- `triggerInstitutionalScan` from `lib/api.ts`

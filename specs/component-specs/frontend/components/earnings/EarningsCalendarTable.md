# frontend/src/components/earnings/EarningsCalendarTable.tsx

**Removed by specs/025-earnings-page-filters.** This was the scored-candidate table shown
after a manual "Scan Earnings" run. The scan trigger was removed from the earnings page
(see `pages/EarningsScan.md`), so this component has no place to render and was deleted
along with its test file. The scan's backend job (`POST /earnings/scan`,
`earnings_scan_worker.py`, `agents/earnings_scanner.py`) still exists but is dormant — see
KNOWN_ISSUES.md.

Replaced by `EarningsTable.md` — the single always-visible results table.

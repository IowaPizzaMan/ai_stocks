# frontend/src/components/earnings/EarningsCandidateCard.tsx

**Removed by specs/025-earnings-page-filters.** This was the score-breakdown detail panel
for a scan candidate. It depended on `EarningsCandidate`/`EarningsScoreBreakdown`
(scan-only types, also removed from `api/types.ts`) and `useEarningsHistory`, both of
which lost their only caller when the scan UI was removed — see `pages/EarningsScan.md`
and KNOWN_ISSUES.md. Deleted along with its test file.

Per-ticker earnings history (`GET /earnings/history/{ticker}`) remains a live backend
endpoint but currently has no frontend consumer.

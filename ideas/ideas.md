# Ideas

Rough notes for future spec work. Items below have been integrated into `specs/` — see the pointer next to each for where it landed. Add new rough notes above the `## Integrated` line as they come up.

## Integrated

- **Switch price data to FMP / research FMP's $20/mo tier further.** → `specs/DATA_SOURCES.md` → "Switching Primary Price Data Source" (still an open decision, not yet made — the write-up captures what needs deciding).
- **Company logos.** → `specs/DATA_SOURCES.md` → "Company Logos", `specs/SPEC.md` → "10. Company Enrichment" (unresearched spike, not built).
- **Company website scraping.** → `specs/DATA_SOURCES.md` → "Company Website Scraping", `specs/SPEC.md` → "10. Company Enrichment" (deferred, same status as Quiver Quantitative).
- **Ticker search filter-as-you-type on the feed.** → `specs/component-specs/frontend/components/feed/FilterBar.md` → "Ticker search" (distinct from the Navbar's existing jump-to-stock search).
- **Trading-strategy filters** (institutions buying/selling, positive/negative on year, "Earning Money", "Stonk"). → `FilterBar.md` → "Strategy Filters (Phase 2)" — spec'd as intent, backing data/thresholds still undecided per the original TBD note.
- **Additional feed flags** (institutional activity, insider transaction summary). → `specs/component-specs/frontend/components/feed/AnalysisCard.md` → "Flag Row", `specs/component-specs/backend/models/analysis.md` → `AnalysisFeedItem`.
- **Sector data for feed filtering.** Already fully built (not just spec'd) — `AnalysisFeedItem.sector`, `GET /analysis/feed?sector=`, `FilterBar`'s sector dropdown.
- **Single chart summarizing all sectors + per-sector strategy analysis.** → `specs/component-specs/frontend/pages/Sectors.md` → "All-Sectors Summary Chart".
- **Clicking a sector jumps to the feed pre-filtered.** → `Sectors.md` — kept the existing richer `/sectors/:sector` heatmap as the primary click target and added a secondary "View in Feed →" link (`/?sector=`) on both the overview cards and the detail page, rather than replacing the detail view.
- **1M chart bug (weekly/monthly change swapped).** → logged to `../KNOWN_ISSUES.md` under "Open bugs" for root-causing, since that's where bugs get tracked here, not `specs/`.

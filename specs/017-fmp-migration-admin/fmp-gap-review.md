# FMP Paid-Plan Gap Review (FR-013)

**Feature**: `017-fmp-migration-admin` · Seeded in Phase 1 (2026-08-15) · **Finalized 2026-08-15 after the user verified entitlements against the live subscription**

Status legend: **adopt** = collect it (market-wide → admin job, ticker-scoped → existing per-ticker flow) · **defer** = later / tier-gated / needs a consuming view first · **reject** = will not collect. *(probe)* = the automated entitlement probe (research D1) still verifies this family before implementation locks it in.

| Dataset family | Final decision | Rationale |
|---|---|---|
| EOD price history | **adopt** (migration) | Replaces yfinance as primary price source (US1) |
| Intraday chart bars | **adopt** (migration) *(probe)* | Replaces yfinance chart resolutions; only entitled resolutions ship |
| Batch quotes | **adopt** (migration) *(probe)* | Cheapest breadth-universe sweep; per-symbol fallback exists (D4) |
| Company info / profile | **adopt** — user confirmed | Per-ticker retrieval flow → `company_info`; reconciles with spec 010's intent (D14) |
| Fundamentals (statements, ratios, key metrics) | adopt (already in use) | Existing FMP integration — unchanged |
| Earnings calendar (windowed) | **adopt** | Feeds earnings scanner without per-ticker yfinance calls |
| Sector performance snapshot | **adopt** | Market Overview core; check overlap with existing Sectors page before adding a second home |
| Market movers (gainers/losers/actives) | **adopt** | Market Overview core; zero-cost daily pull |
| Economics — economic data releases | **adopt** — user confirmed | `economics_pull` → `economic_calendar_events` (D13) |
| Economics — treasury rates | **adopt** — user confirmed | Full-curve daily snapshot → `treasury_rates`; FRED keeps its existing long-history series (D13) |
| Economics — economic indicators | **adopt (non-FRED series only)** — user confirmed | FRED stays canonical for its 12 existing series (FR-016, D13); FMP fills gaps |
| Economics — market risk premium | **adopt** — user confirmed | Not available from FRED → `market_risk_premium` (D13) |
| Insider trading (per-ticker + market-wide feed) | **adopt** — user confirmed entitled | `insider_feed_pull` job + existing per-ticker insider collection stays FMP |
| Senate & house trading | **adopt** — user confirmed entitled | `congress_trades_pull`; replaces the deferred paid-Quiver plan for this signal |
| ETF & mutual-fund holdings | **adopt** — user confirmed entitled | `fund_holdings_pull`; **replaces the Dataroma superinvestor scraper, which is retired** (D11) |
| Market news + per-ticker stock news | **adopt** — user confirmed | Per-ticker news on retrieval → `stock_news` + StockDetail; `market_news_pull` → Feed page section; feed redesign deferred (D12). FMP owns articles; Finnhub keeps sentiment aggregates (FR-016) |
| Analyst grades / price-target summaries | adopt *(probe)* | Replaces yfinance analyst block; ticker-scoped → StockDetail |
| Index constituent lists | adopt (already in use) | Breadth already uses these — unchanged |
| 13F institutional ownership | **defer — NOT entitled** (user verified) | Out of scope; user will source 13F outside FMP later. Live holder-table refresh drops per migration-map row 6 |
| Earnings-call transcripts | **defer — NOT entitled** (user verified) | Out of scope from FMP; Finnhub remains the transcript source of record |
| IPO / dividend / split calendars | defer | No consuming view yet — revisit after Market Overview lands |
| ESG scores | defer | Nothing consumes ESG today; adopt only with a consuming view |
| Executive compensation / M&A / delistings | defer | No consuming feature; logged for future ideas |
| Commitment of Traders | defer | Interesting macro signal, no consuming view yet |
| Technical indicators (FMP-computed) | reject | Computed locally by the deterministic skills layer (constitution III) — never outsourced |
| Forex | reject | Not equities; same logic as crypto — user may veto this extrapolation |
| Crypto (all endpoints) | **reject (mandated)** | Explicitly excluded by the user (FR-013) |

## Superinvestor signal gap (accepted)

Retiring Dataroma + no 13F entitlement means true superinvestor-portfolio tracking (Berkshire, Pershing, …) pauses. ETF & fund holdings is the interim adjacent signal. Options when revisited: SEC EDGAR 13F-HR (free, already documented in `specs/DATA_SOURCES.md`), Quiver `sec13F` ($30/mo), or an FMP plan upgrade. Recorded as a future feature, not part of 017.

## Entitlement probe results

*To be appended by the `fmp_entitlement_probe` admin job during implementation — one row per remaining ambiguous family (batch quotes, intraday resolutions, analyst grades): probed endpoint, HTTP status, result, checked-at. User-verified families above may be spot-checked but are considered settled.*

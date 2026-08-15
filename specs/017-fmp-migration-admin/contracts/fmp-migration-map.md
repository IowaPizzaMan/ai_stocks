# Contract: yfinance → FMP Migration Map

**Feature**: `017-fmp-migration-admin` · Phase 1 output
**Consumers**: implementers of every migrated call site; the FR-003 disposition record lives here.

Base URL: `https://financialmodelingprep.com/stable/` (already used by `tools/financials.py`; the `v3`/`v4` paths in `specs/DATA_SOURCES.md` are legacy and get rewritten under FR-007). All calls go through the shared `fmp_client.py` (throttle + budget guard + fail-soft, research D5). "Probe family" refers to `fmp_entitlements.family` (research D1); a `payment_required` probe activates the listed fallback.

## Call-site map

| # | Call site | yfinance today | FMP stable target | Probe family | Fallback if tier-gated |
|---|---|---|---|---|---|
| 1 | `agent-runner/data_fetcher.py` §1 + `tools/price.py` daily bars | `yf.download` / `Ticker.history` daily | `historical-price-eod/full?symbol=` (dividend+split-adjusted variant per D3) | `eod_prices` | none expected — EOD is in every paid tier; if probe fails, migration blocks (raise to user) |
| 2 | `backend/routers/price.py` + `tools/price.py` intraday bars (1m…1h resolutions) | `Ticker.history(interval=…)` | `historical-chart/{1min|5min|15min|30min|1hour|4hour}?symbol=` | `intraday_1h`, `intraday_1m` (probe finest + coarsest) | serve only entitled resolutions; chart resolution picker hides unavailable ones; document dropped resolutions in gap review |
| 3 | `agent-runner/tools/breadth.py` universe closes + SPY | batched `yf.download` | batch quote (comma-separated symbols) for daily sweep | `batch_quote` | per-symbol `historical-price-eod` delta through throttle (research D4) |
| 4 | `agent-runner/tools/earnings_calendar.py` `get_earnings_history()` — dates + price series for the post-earnings reaction-move calc | `Ticker.get_earnings_dates` + `Ticker.history` | `earnings?symbol=` (per-ticker dates) + `historical-price-eod/full` (row 1's fetch) | `earnings_calendar` | Finnhub `stock/earnings` for dates if needed (calendar itself already Finnhub-sourced via `get_earnings_calendar()` — no yfinance there, out of scope) |
| 5 | `agent-runner/tools/financials.py` earnings block (estimates, revisions, analyst recs) + `agent-runner/agents/earnings_scanner.py` `_eps_revision_direction()` (discovered during implementation — a 9th yfinance call site not caught during planning) | `Ticker.get_earnings_estimate/…`, `Ticker.get_eps_revisions()` | analyst estimates + grades family (`analyst-estimates`, `grades`, `price-target-summary`); `_eps_revision_direction()` uses recent `grades` upgrade/downgrade counts as an analyst-sentiment-direction proxy (not a literal EPS-number-revision count — the closest FMP-native signal, documented substitution) | `analyst_grades` | Finnhub `stock/recommendation` + `stock/price-target` (already integrated); anything with no fallback → documented drop below |
| 6 | `agent-runner/data_fetcher.py` §6 + `tools/institutional.py` holder tables | `get_institutional_holders` etc. | FMP ownership family (13F/holders) | `form_13f` — **RESOLVED: not entitled (user-verified 2026-08-15)** | **Drop of live refresh confirmed** — existing stored holder data retained read-only; InstitutionalFlow degrades to stored data + the new `fund_holdings` and `insider_feed` datasets. Revisit when 13F is sourced outside FMP (future feature). |
| 7 | `agent-runner/crew.py` ticker existence / delisting check | yfinance lookup success/failure | `quote?symbol=` — empty/404 ⇒ delisted-candidate (same `TickerDelistedError` semantics) | `eod_prices` | n/a (same family as #1) |
| 8 | `agent-runner/tools/earnings_calendar.py` price context | `Ticker.history` | same as #1/#2 | `eod_prices` | n/a |

## FR-003 dispositions (Yahoo data with no FMP path on the current plan)

Final column resolved by the probe; recorded here as the authoritative disposition list, mirrored into `specs/DATA_SOURCES.md`:

| Yahoo-provided item | Disposition |
|---|---|
| Options chains (`option_chain`) | **Drop** — never wired into any view/agent; no FMP equivalent on typical tiers |
| ESG scores (`get_sustainability`) | **Drop** — not consumed anywhere in code today; FMP ESG is tier-gated; gap review may re-adopt on entitlement |
| Real-time streaming (`.live()` WebSocket) | **Drop** — never used; no-polling constitution rules it out anyway |
| Institutional holder tables | **Resolved: drop live refresh** — `form_13f` not entitled (user-verified); stored data read-only, `fund_holdings` + `insider_feed` are the replacement signals (row 6 above) |
| Analyst estimate detail (EPS trend/revisions granularity) | **Conditional** — FMP `analyst_grades` if entitled, else Finnhub covers recs/targets; finer revision detail dropped |
| Deep price history (>FMP plan window) | **Preserved** — already cached in Mongo, never refetched (research D3) |
| News (`get_news`) | **Already owned by Finnhub** — no change |

## Removal gate

Migration is complete when: `yfinance` absent from both `requirements.txt` files; `grep -ri yfinance backend/ agent-runner/ scripts/` returns only comments/specs (target: zero code hits); all existing pytest suites green with FMP fakes (SC-002/SC-003). `specs/data_fetcher.py` (spec copy) is updated alongside `agent-runner/data_fetcher.py`.

# Research: Stocks Page News Tab and Cross-Stock AI Summary

Every "NEEDS CLARIFICATION" in the Technical Context is resolved below by reading the
existing codebase rather than guessing — this feature reorganizes and extends
patterns that already exist elsewhere in the app.

## R1 — Bounded layout, scoped to the Stocks page only

**Decision**: Give `Stocks.tsx`'s own root element a viewport-relative bounded height
(`flex flex-col` with something like `h-[calc(100vh-Nrem)]`, N tuned during
implementation to whatever the Navbar + `main`'s padding actually consume) containing
two regions: a non-shrinking header (title/filter bar/tab bar) and a `flex-1
overflow-y-auto` body that holds the active tab's content (digest + grid, or the News
list). Do **not** touch `App.tsx`, `Navbar.tsx`, `Sidebar.tsx`, or any other page.

**Rationale**: The user's ask ("the main page has no scroll") is scoped to the Stocks
page in context — every other route (`Macro`, `StockDetail`, `Sectors`, `Watchlist`,
`EarningsScan`, `InstitutionalFlow`) still relies on ordinary document-level scroll
today via the shared `min-h-screen` shell in `App.tsx`. Converting that shared shell to
a fixed-height/`overflow-hidden` layout would force every other page to grow its own
internal scroll region too — a much larger, riskier change than what was asked, and
against Constitution V (no incidental scope growth). A page-local bounded container
achieves the same visible effect (filter bar and tabs always in view, only the grid/news
list scrolls) with zero blast radius on other routes.

**Alternatives considered**: Global `App.tsx` shell rework (`h-screen overflow-hidden` +
`main` as the scroll surface) — rejected: touches six unrelated pages for a request
scoped to one. `sticky` positioning on the filter/tab header instead of a bounded
container — rejected: doesn't stop the grid from growing the page itself, so the
browser window would still scroll past the sticky header, which is exactly the
behavior being removed.

## R2 — Removing auto-fetch-on-scroll from the grid

**Decision**: Delete the `useIntersectionObserver` wiring and its sentinel `<div
ref={loadMoreRef}>` from `Stocks.tsx`. Keep `useFeed`'s existing server-side pagination
(`useInfiniteQuery`, `page_size: 60`) exactly as-is; add a visible "Load more" button
that calls `fetchNextPage()` when `hasNextPage && !isFetchingNextPage`, mirroring the
button already used for the Feed's page-count semantics — the button is new UI, the
underlying network pattern (`GET /analysis/feed?page=N&page_size=60`) is unchanged.

**Rationale**: The "no infinite scroll" complaint is about the *auto-fetch-on-scroll*
UX pattern (`useIntersectionObserver`, used only here and on `InstitutionalFlow.tsx` in
the whole app), not about the grid's underlying pagination strategy, which is already
efficient. Swapping the trigger from "scroll near the bottom" to "user clicks a button"
is the minimal change that satisfies the requirement.

**Alternatives considered**: Rewriting the grid to client-side-slice a single large
fetch (the per-ticker News tab's `PAGE_SIZE`/`visible`-state pattern) — rejected: that
pattern exists because `NewsTab.tsx` already has the *entire* article set in memory
from one request; the grid's data is genuinely paginated server-side and re-fetching
everything in one call would be a regression, not a simplification.

## R3 — Stocks page tabs

**Decision**: Add a small `TABS` array (`grid` default, `news`) and hash-based active-tab
routing to `Stocks.tsx`, matching the pattern `StockDetail.tsx` already uses
(`location.hash`, unknown/absent hash falls back to the default tab, `navigate(#id,
{replace:true})` on click). Extract the tab-button `<nav>` markup the two pages would
otherwise duplicate into a small shared `frontend/src/components/shared/TabBar.tsx`.

**Rationale**: Constitution VI (consistency across layers) and plain reuse — the
detail page has already solved "tabs with a bookmarkable default-falls-back hash" once;
copying the same shape avoids inventing a second tab convention in the same app.

**Alternatives considered**: URL search param for the active tab (`?tab=news`) instead
of a hash — rejected: would be inconsistent with the one tabbed page that already
exists, and the Stocks page's search params are already claimed by the filter bar
(`ticker`, `signal`, `sector`, `conviction` — see `FilterBar.tsx`), so a hash avoids any
key collision risk between "which tab" and "how the grid is filtered."

## R4 — Regeneration runs through the existing (currently unused) admin-job path

**Decision**: Register a new `work_queue` `job_type` of `"portfolio_digest"` in
`agent-runner/tools/admin_jobs.py`'s `JOB_HANDLERS`, backed by a new handler function.
Add a `POST /portfolio/digest/regenerate` backend endpoint that inserts a
`job_type="portfolio_digest"` document into `work_queue` (deduped against an
already-pending/running one, mirroring `queue.py`'s `_enqueue` ticker-job dedupe).

**Rationale**: `agent-runner/queue_worker.py`'s `claim_and_run_next` already branches on
`job_type` for non-ticker ("admin") jobs (`_run_admin_job`, dispatching through
`JOB_HANDLERS`) — this exists today for `economics_pull`, but that job type actually
runs on its own daily timer (`economics_worker.py`) and nothing in the current codebase
ever enqueues a `work_queue` document to exercise the admin-job dispatch path. This
feature becomes the first thing that actually drives it end-to-end, using
infrastructure that already exists rather than adding a second queue, a new service, or
a new scheduler (Constitution V forbids exactly that). It also means the frontend's
existing busy/in-progress mechanism (`GET /queue`, `pending`/`running` arrays) already
works for this job with no backend queue-shape changes.

**Alternatives considered**: A dedicated `POST /portfolio/digest/regenerate` that runs
the synthesis synchronously in the request handler — rejected: an LLM call belongs off
the request thread like every other analysis step in this app, and the frontend has no
other pattern for "block on a slow POST." A brand-new lightweight queue just for this
job — rejected: `work_queue` already supports non-ticker jobs; a second queue would
violate Constitution V and VI.

## R5 — Synthesis input: source, shape, and cap

**Decision**: The input set is every document in `analyses` (`ANALYSES` collection) —
this collection already holds exactly one document per ticker (`write_db(...,
upsert_key="ticker")`, unique index on `ticker`), so it *is* "every tracked stock's most
recent analysis" with no extra dedupe step needed. Each stock is condensed to `{ticker,
signal, conviction, summary, key_trends, flags, news_stance}` before it reaches the
prompt — the same "trim the bulky stuff, keep the assessments" move
`portfolio_strategist.py` already makes per-ticker. When more than **25** stocks have a
stored analysis, the condensed list is sorted by conviction (high → medium → low, ties
broken by most-recently-analyzed) and truncated to the top 25 (clarified 2026-08-21:
highest-conviction first), with the response noting how many were included vs. tracked.

**Rationale**: 25 condensed entries at roughly 150–300 tokens each comfortably fits
inside Ollama's `DEFAULT_OPTIONS["num_ctx"] = 8192` (`llm.py`) alongside the system
prompt and instructions, without needing a bigger context window or chunking. The exact
number is a tuning knob, not a business rule (the spec deliberately left it to
planning) — 25 is the concrete starting value for implementation and tests; it can be
adjusted later without a spec change.

**Alternatives considered**: Feeding full per-ticker `sub_reports` (technical/
fundamental/insider/institutional narratives in full) — rejected: that's the shape
`AISummaryTab` renders per ticker and is far too large across dozens of tickers; the
top-level `Analysis` fields (`summary`, `key_trends`, `flags`, `signal`, `conviction`)
plus the news stance are what a synthesis actually needs, matching what
`portfolio_strategist.py` already treats as "the assessments, not the raw series."

## R6 — Persisting the digest and representing staleness

**Decision**: One singleton document in a new `portfolio_digest_cache` collection
(no key filter needed — `find_one({})`, matching the existing `MARKET_RISK_PREMIUM`
singleton-document pattern) carries both the last successful result (`generated_at`,
`overview`, `highlights`, `stock_count`, `total_tracked_count`, `capped`) and the last
failure (`last_error`, `last_error_at`), updated independently. `GET /portfolio/digest`
derives `stale: bool` by comparing `last_error_at` to `generated_at` (an error strictly
newer than the last success ⇒ stale) rather than reading any `work_queue` state.

**Rationale**: Mirrors `backend/routers/market.py`'s existing `_stale()` helper for
market news — "keep serving the last good copy, mark it plainly, never let a refresh
failure blank the panel" (FR-011, FR-012) — applied to a single evolving document
instead of a replace-on-success cache row, since here (unlike market news) success and
failure need to be visible independently across visits, not just within one request.

**Alternatives considered**: Deriving staleness from the `work_queue` job's terminal
`status` — rejected: a `"failed"` job leaves `pending`/`running` the moment it
terminates, so nothing would still be observable by the time a user loads the page on
their next visit; the failure has to be recorded somewhere durable.

## R7 — "Busy while regenerating" reuses the existing queue-status mechanism

**Decision**: The frontend detects an in-flight regeneration exactly the way
`StockDetail.tsx` already detects a running Pull: read `GET /queue`'s `pending`/
`running` arrays (via the existing `useQueueStatus` hook, which already polls only
while something is busy and goes quiet otherwise) and look for an entry with
`job_type === "portfolio_digest"`. `QueueJob.ticker` becomes optional in
`api/types.ts` to represent this admin-job shape (no ticker).

**Rationale**: Constitution's Tech Stack Constraints mandate `refetchInterval: false`
everywhere except this one sanctioned exception, which already exists and already
invalidates the right query keys on drain (`useQueueStatus`'s `refetchInterval`
callback) — adding `["portfolio-digest"]` to that invalidation list is the only change
needed there.

**Alternatives considered**: A new polling hook dedicated to the digest job —
rejected: duplicates `useQueueStatus` for no reason and would be a second exception to
the no-polling rule.

## R8 — Filter independence

**Decision**: `usePortfolioDigest()` takes no arguments and puts no filter state in its
query key, and the backend endpoint reads all of `analyses` unconditionally —
changing the Stocks page's filter bar (`ticker`/`signal`/`sector`/`conviction` URL
params) never affects the digest panel or triggers a recompute (clarified 2026-08-21).

**Rationale**: Directly mirrors `useMarketNews()`'s existing filter-independence
(`specs/022`, FR-001b) — same shape of problem, same already-validated answer.

## R9 — Digest panel placement: side-by-side with the grid, not stacked

**Decision**: On the default (`grid`) tab, `Stocks.tsx` renders the grid and
`<PortfolioDigestPanel />` as two columns inside the scrollable body (e.g. a
`flex`/`grid` row with the grid in the first/primary column and the digest panel in a
second, narrower column alongside it), not the digest panel stacked above the grid.

**Rationale**: Clarified 2026-08-22 (FR-007b) — the user explicitly asked for the
digest ("news and analysis section") to sit beside the tickers rather than above them.
Both regions still live inside the single `flex-1 overflow-y-auto` scroll container
from R1; only their internal arrangement (row of two columns vs. one stacked column)
changes. At narrow viewports the columns can wrap to stacked (grid first) without
violating FR-007b, since FR-007b governs relative reading order/position, not a
fixed-width breakpoint behavior.

**Alternatives considered**: Digest panel stacked above the grid (the original,
pre-clarification implementation) — superseded by FR-007b. Digest panel below the grid
— rejected for the same reason (spec calls for side-by-side, not another stacked
order). A completely separate sub-tab for the digest — rejected: FR-007 requires the
digest to be part of the default tab, visible without an extra click.

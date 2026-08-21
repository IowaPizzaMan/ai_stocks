# Phase 0 Research: Delta-Only Data Pulls

**Feature**: `specs/024-delta-data-pulls` | **Date**: 2026-08-17

All findings below were verified against the repository as it stands on branch
`cache_miss_issue`. No live API probing was needed — every provider capability this
plan depends on is already exercised by existing code, cited per decision.

---

## D0: What a pull actually costs today (baseline)

**Finding**: A single ticker pull (`agent-runner/crew.py::Crew._prefetch`) issues
roughly 18–22 external requests, and downloads the ticker's **entire** EOD price
history **twice**.

| Stage | Source | Requests | Payload character |
|---|---|---|---|
| `price` | FMP `historical-price-eod/full` | 1 | Full history (all available years) |
| `indicators` | FMP `historical-price-eod/full` | 1 | **Same full history, fetched again** |
| `financials` | FMP × 7 statements | 0 or 7 | 90-day cache, usually 0 |
| `earnings` | FMP × 3 | 3 | Small |
| `insider` | Finnhub × 2 | 2 | 90-day window |
| `insider_stats` | FMP | 1 | Small |
| `institutional` | — | 0 | Read-only from cache already |
| `beneficial` | FMP | 1 | 7-day TTL cache |
| `sentiment` | Finnhub × 2 | 2 | Small |
| `news` | FMP `news/stock` | 1–5 pages | Article bodies — large |
| `breadth` | shared | 0 | Cross-ticker cache |

The duplicate history fetch is at [crew.py:143-144](../../agent-runner/crew.py#L143-L144):
`get_price_history` and `get_technical_indicators` each independently call
`fetch_eod_history`. A third caller, `get_accumulation_score`
([price.py:109](../../agent-runner/tools/price.py#L109)), does the same when invoked.

Separately, the backend keeps **four** price cache documents per ticker — one per
chart resolution ([routers/price.py:28-33](../../backend/routers/price.py#L28-L33)) —
each triggering its own full download on expiry, even though agent-runner already
proves all resolutions resample from one daily series
([tools/price.py:44-52](../../agent-runner/tools/price.py#L44-L52)).

---

## D1: Delta price fetches save bytes, not API calls — and that reframes the goal

**Decision**: Treat SC-001 (50% faster) as **unproven** until US1 measures it, and
build US1 first exactly as the spec prioritizes.

**Rationale**: FMP's `historical-price-eod/full` costs **one request** whether or not
a `from=` bound is supplied. So for price — the largest payload — delta fetching
reduces *transfer and parse time*, not request count. The saving is real (a 15-year
history versus two days of bars) but it is bounded by what fraction of pull wall-time
is actually spent on HTTP transfer and pandas parsing, rather than on the sequential
LLM agent calls that follow.

News is different: `news/stock` pages backwards at 250 articles per request, so a
narrow delta window genuinely **eliminates requests** (typically 5 pages → 1).

This is the single most important finding in this document. It does not change what
gets built, but it changes what we expect: the wins are (a) eliminating the duplicate
full history download, (b) eliminating three of four chart-resolution downloads, and
(c) collapsing news paging. If US1 shows LLM time dominates, SC-001's target must be
restated against the data-fetch portion of the pull rather than the whole thing.

**Alternatives considered**: Building the delta layer first and measuring afterwards
— rejected, because it risks a large refactor that moves a number nobody has measured.

---

## D2: Provider support for bounded requests — already proven in-repo

**Decision**: No live probing required. Use the bounded forms already in use.

| Dataset | Bounded form | Already used at |
|---|---|---|
| EOD prices | `historical-price-eod/full?symbol=X&from=YYYY-MM-DD` | [backend/routers/price.py:83-86](../../backend/routers/price.py#L83-L86) |
| Stock news | `news/stock?symbols=X&from=&to=&limit=&page=` | [tools/news.py:128-132](../../agent-runner/tools/news.py#L128-L132) |
| Insider transactions | Finnhub `stock/insider-transactions` with `from`/`to` | [tools/insider.py:150-156](../../agent-runner/tools/insider.py#L150-L156) |
| Earnings history | FMP `earnings?symbol=X&limit=N` | [tools/financials.py:114](../../agent-runner/tools/financials.py#L114) |

**Caveat on earnings**: `earnings` is bounded by `limit`, not by date. It is already
effectively incremental (limit 8) and small. Per the spec's assumption that not every
dataset is a delta candidate, it is **excluded** — the delta work for US4 targets
insider transactions only, where a date bound exists.

---

## D3: Storage — one shared daily price series per ticker

**Decision**: Introduce a `price_history` collection holding **one document per
ticker**: the full daily OHLCV series plus a coverage envelope. Both containers read
and write it. Retire the backend's four-doc-per-ticker `price_cache`.

**Rationale**: This one change satisfies four requirements at once:

- **FR-015/FR-016 + SC-004** — every chart resolution resamples locally from the
  stored daily series, so switching resolutions triggers zero downloads.
- **FR-014 + SC-003** — the store *is* the deduplication. Once `price`, `indicators`,
  and `accumulation` all read the stored series, no memoization layer is needed to
  stop them fetching twice.
- **FR-025/FR-030** — one document per ticker means a full refresh is a single atomic
  `replace_one`. Build the new series fully in memory, then swap. A failed refresh
  cannot leave a half-written series, because the write never starts.
- **FR-031** — single-document atomicity also removes the interleaving hazard between
  a backend page-load fetch and an agent-runner pull.

**Alternatives considered**:
- *One document per bar* — natural for appends and range queries, but turns a series
  read into thousands of documents, loses the atomic-swap property that gives FR-030
  for free, and is far more machinery than a single-user local stack needs
  (Principle V).
- *Keep `price_cache` and add deltas to it* — rejected; the per-resolution layout is
  the direct cause of SC-004's problem, so preserving it defeats the purpose.

**Document size check**: 15 years of daily bars ≈ 3,800 rows. At ~120 bytes per BSON
row that is ~450 KB — comfortably inside MongoDB's 16 MB document limit, with roughly
30× headroom.

---

## D4: Cross-container duplication — follow the established precedent

**Decision**: Implement the store accessor twice — `agent-runner/tools/price_store.py`
and `backend/price_store.py` — kept in sync by hand, with a header comment on each
pointing at the other.

**Rationale**: Constitution Principle V forbids a shared package; Principle VI demands
semantic consistency. The repo already resolves this tension the same way three times:
collection constants in `db.py`, `backend/fmp.py` mirroring `tools/fmp_client.py`, and
`backend/earnings_data.py` mirroring `tools/earnings_calendar.py`. This is the
house pattern, not a new exception.

**Mitigation for the drift risk this creates**: the merge/coverage logic is the part
that must not diverge, so it is written as **pure functions over plain data** (no
Mongo, no HTTP) and each service's test suite runs the *same* table of merge cases.
Divergence then shows up as a test failure rather than as silent data corruption.

---

## D5: The overlap margin — how to not skip a day

**Decision**: Request from `newest_stored_date − 1 day`, never from
`newest_stored_date + 1 day`, and rely on idempotent merge to discard the overlap.

**Rationale**: The spec's clock/timezone edge case is a real hazard — provider day
boundaries, exchange timezones, and UTC storage do not agree, and an off-by-one on the
exclusive side silently drops a trading day forever. Re-requesting one day that is
already held costs nothing measurable (one extra row) and is provably safe once merge
is idempotent. Erring toward overlap converts a silent-corruption bug into a no-op.

**Consequence**: merge must be keyed on a natural identity — `date` for bars, `url` for
articles, `(filingDate, name, transactionType)` for insider rows — and must overwrite
rather than append on a key collision, so a corrected record replaces its predecessor.

---

## D6: Explicit refresh, not implicit freshness

**Decision**: The store accessor takes an explicit mode:
`get_series(ticker, refresh="none" | "delta" | "full")`. The crew refreshes **once**
at the start of prefetch; every later reader in the same pull passes `refresh="none"`.

**Rationale**: The alternative — a short "already refreshed recently" TTL — reintroduces
exactly the implicit time-based freshness this feature exists to remove, and makes
tests depend on wall-clock timing. An explicit mode is honest about intent, trivially
testable, and makes FR-014 a structural property rather than a coincidence.

---

## D7: Attributing requests and bytes to stages (US1)

**Decision**: A thread-local "current stage" set by a `stage_recorder(name)` context
manager, read by the HTTP clients (`tools/fmp_client.py::fmp_get`,
`tools/finnhub_client.py::finnhub_get`) when they tally a call.

**Rationale**: `_prefetch` runs either sequentially or inside a `ThreadPoolExecutor`
([crew.py:155-159](../../agent-runner/crew.py#L155-L159)). Python's `ThreadPoolExecutor`
does **not** propagate `contextvars` into pool workers, so a contextvar-based approach
would silently record nothing in the parallel path — the exact path used by
earnings-scan pulls. A `threading.local` set *inside* each job's callable works in both
modes, because each pool worker runs one stage at a time on its own thread.

Bytes come from `len(response.content)` at the same chokepoint. Both clients already
funnel every call through a single function, so there is one place to instrument per
service.

**Alternatives considered**: passing an accumulator object through every fetch
signature — correct but viral, touching a dozen call sites for a diagnostic; a
`requests` transport adapter/hook — global, and harder to attribute to a logical stage.

---

## D8: Pull mode plumbing

**Decision**: Add `mode: "delta" | "full"` to the `work_queue` job document, defaulting
to `"delta"` when absent. Surface it as an optional parameter on the existing
`POST /queue/{ticker}` endpoint rather than adding a second endpoint.

**Rationale**: One enqueue path is easier to keep correct than two, and the queue
document already carries per-job options in exactly this style
(`parallel_prefetch`, [queue_worker.py:139](../../agent-runner/queue_worker.py#L139)).
Absent-means-delta keeps every existing enqueue call site and any in-flight job valid
with no migration.

**Upgrade-in-place wrinkle**: `_enqueue` currently short-circuits to `already_queued`
when a pending/running job exists ([routers/queue.py:35-37](../../backend/routers/queue.py#L35-L37)).
A full-refresh request arriving while a delta job is *pending* must **upgrade that job
to full** rather than report "already queued" — otherwise the operator presses the
button, is told it is already handled, and gets a delta pull. If the existing job is
already `running`, it is too late to upgrade; report that plainly so the operator can
retry once it lands.

---

## D9: Full refresh respects the budget cap (FR-027)

**Decision**: No new budget logic. A full refresh calls the same `fmp_get`/`fmp_client`
path, so `FmpBudgetExceededError` surfaces and every existing fail-soft handler applies
unchanged.

**Rationale**: Constitution Principle IV, and the clarified answer to Q3. The cap is
checked *before* the request goes out
([fmp.py:55-61](../../backend/fmp.py#L55-L61)), so a blown budget never spends the call
it was meant to prevent. The only new work is reporting: FR-028 requires the operator
to see that the refresh degraded rather than completed, which the pull-metrics record
from US1 already carries.

**Note**: two backend call sites still bypass the counter
(`backend/routers/price.py`, `backend/earnings_data.py::_fmp_get`) — a known issue
already logged in `KNOWN_ISSUES.md`. This feature rewrites the first of those anyway,
so routing it through `backend/fmp.py::fmp_get` is folded in at no extra cost. The
`earnings_data.py` site stays out of scope.

---

## D10: Where the operator sees pull cost (SC-006)

**Decision**: Store one `pull_metrics` document per pull; expose it via a backend
endpoint; render a compact collapsible panel on the existing StockDetail page. **No new
page or admin route.**

**Rationale**: The frontend has seven routes and no admin surface. SC-006 needs the
three most expensive stages to be visible without reading logs — a panel on the page
where the pull is triggered satisfies that at the lowest possible cost, and puts the
diagnostic next to the button that produced it. Adding an admin section would be
infrastructure ahead of demonstrated need (Principle V).

**Retention**: `pull_metrics` gets a TTL index (30 days). It is diagnostic data, and
FR-003 only requires enough history to rank stages over time.

---

## D11: When a delta window is too wide to bother (FR-011)

**Decision**: If the stored series' newest bar is more than **2 years** old, fetch
full instead of delta.

**Rationale**: Since a bounded EOD request costs the same one call as an unbounded one
(D1), the only thing a very wide delta window buys is a larger, more awkward merge
against a stale baseline. Past roughly the point where the delta window rivals the
useful history length, a clean full fetch is simpler and no more expensive. Two years
is chosen because it matches the shortest resolution window the app actually serves
(`daily: 2y`), so any gap wider than that means the stored series cannot satisfy even
the default chart without backfill.

For news the equivalent rule is implicit: the window is capped at `NEWS_DAYS` (30)
regardless, so a long-dormant ticker naturally falls back to a full-window fetch.

---

## D12: Testing approach

**Decision**: Pure-function merge/coverage logic tested exhaustively with a shared case
table; HTTP mocked at the client chokepoint; no live provider calls in tests.

**Rationale**: Constitution Principle I. The merge logic is where correctness lives and
it is fully deterministic, so it is the highest-value test surface — the same argument
the constitution makes for the rule-engine skills. Both services run the same case
table (D4), which is what actually enforces Principle VI here.

Required coverage per the spec's edge cases: empty baseline, exact-boundary overlap,
gap in the middle, out-of-order rows, duplicate keys, corrected/restated record
replacing an older one, non-trading-day (empty delta), oversized gap triggering full,
partial failure retaining what was fetched, and interrupted full refresh leaving the
prior series intact.

---

## Resolved unknowns

| Unknown from Technical Context | Resolution |
|---|---|
| Do providers support bounded requests for the targeted datasets? | Yes for prices, news, insider — all already used in-repo (D2). Earnings is limit-bounded, excluded (D2). |
| Where does shared price state live given no shared package? | New `price_history` collection, duplicated accessor per the house pattern (D3, D4). |
| How are per-stage requests attributed under parallel prefetch? | `threading.local`, not `contextvars` (D7). |
| How does a full refresh avoid destroying good data on failure? | Build in memory, single atomic document swap (D3). |
| Does delta fetching reduce the FMP daily call count? | For news yes; for prices no — it reduces bytes only (D1). |
| What surfaces the pull-cost breakdown? | Panel on existing StockDetail, no new route (D10). |

No `NEEDS CLARIFICATION` markers remain.

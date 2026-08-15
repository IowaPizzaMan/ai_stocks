# Data Model: Deduplicate Analysis Feed & Storage

No new entities are introduced. This feature changes the **cardinality invariant** of an
existing entity and removes a now-orphaned collection field's multiplicity, plus adds one
index.

## Analysis

Stored in MongoDB collection `analyses` (`ANALYSES` constant, `agent-runner/tools/db.py:12`
/ `backend/db.py:10`).

| Field | Type | Notes |
|---|---|---|
| `ticker` | string | Uppercase symbol. **Becomes the natural key** — see Invariant below. |
| `timestamp` | datetime | When this analysis completed. Used for sort/latest determination. |
| `signal` | string | `"bullish"` \| `"bearish"` \| `"neutral"` |
| `conviction` | string | `"high"` \| `"medium"` \| `"low"` |
| `summary` | string | |
| `key_trends` | string[] | |
| `flags` | string[] | |
| `sector` | string \| null | |
| `position_management` | object | |
| `recent_institutional_activity` | `"buying"` \| `"selling"` \| `"mixed"` \| null | Feed-only flag; may be absent on older docs |
| `recent_insider_summary` | string \| null | Feed-only flag; may be absent on older docs |
| `sub_reports` | object | technical/fundamental/macro/insider/institutional/sentiment/recommendation; large — always projected out of Feed/list responses |

### Invariant change (this feature)

**Before**: Zero or more `Analysis` documents may exist per `ticker` (one per completed
run, unboundedly growing).

**After**: At most one `Analysis` document exists per `ticker` at any time. A new completed
run for a ticker **replaces** that ticker's existing document (same `ticker`, new data) —
see `research.md` D1. This makes `ticker` the effective natural key of the collection.

### Index changes

| Index | Status |
|---|---|
| `{ticker: 1, timestamp: -1}` | Existing (`agent-runner/tools/db.py:49`, `backend/db.py:37`) — kept, still useful for the dedupe script's per-ticker latest lookup and for `get_latest_analysis()` (`agent-runner/tools/db.py:91-93`). |
| `{timestamp: -1}` | Existing (`backend/db.py:38`) — kept, feed sort. |
| `{ticker: 1}` **unique** | **New** (D6). Enforces the invariant at the database level as defense-in-depth beyond the D1 upsert. Creation is fail-soft (logs + continues) if pre-existing duplicates block it — see `research.md` D6. |

### Relationships / consumers affected by the invariant change

- **Feed** (`GET /analysis/feed`): no query change; correctness now follows directly from
  the invariant (`research.md` D2).
- **Sector view** (`GET /analysis/sector/{sector}`, `GET /sectors`): unchanged — its existing
  `$group`-by-ticker aggregation becomes redundant but harmless; out of scope to remove
  (`research.md` D2).
- **Per-ticker lookup** (`GET /analysis/{ticker}`): response shape changes from array to
  single object/null, since the invariant means there is never more than one to return
  (`research.md` D3; see `contracts/`).
- **Ticker removal** (`backend/routers/stocks.py:90`, `db[ANALYSES].delete_many({"ticker": ticker})`):
  unaffected — still deletes the (now singular) analysis doc for a removed ticker.
- **Signals lookup** (`backend/routers/stocks.py:146`) and **search enrichment**
  (`backend/routers/stocks.py:37-53`): both already use `find_one(..., sort=[("timestamp", -1)])`
  — already latest-only, unaffected by this change.

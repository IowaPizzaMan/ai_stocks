# Contract: `screener` Collection & Signal Computation

**Feature**: `031-semantic-layer-chat`
**Producer**: `agent-runner/tools/screener.py` · **Consumer**: `backend/semantic/`

Field definitions live in [data-model.md](../data-model.md). This document fixes the *contract*
between the two services — the part Principle VI says must not drift.

---

## Producer contract

### Pure computation (the tested surface)

```python
def compute_signals(
    bars: list[dict],            # price_history.bars — ascending by date
    financials: dict | None,     # financials_cache.data
    profile: dict | None,        # company_info.profile
    *, ticker: str, is_tracked: bool,
) -> dict:
    """Deterministic. No I/O, no LLM, no clock reads beyond an injected timestamp."""
```

Mandatory properties — these are the test contract (Principle I, Principle III):

1. **Pure**: same inputs → identical output. No network, no database, no `datetime.now()`
   inside; the timestamp is injected.
2. **Total**: never raises on malformed input. Missing/short/dirty data yields `null` fields,
   never an exception and never a fabricated zero.
3. **Guarded division**: zero-width 20-day range → `range_pct_20d = null`; zero stdev →
   `zscore_20d = null`.
4. **Threshold**: `<25` bars → all price signals `null`, `insufficient_history = true`.
5. **Coercion**: `$numberLong` / `Decimal128` coerced to plain numbers before comparison.
6. **Tri-state trends**: `financials_trend` and `margin_trend` return exactly
   `"improving" | "flat" | "deteriorating" | null` — never a free-form string.

### Persistence

```python
db[SCREENER].replace_one({"ticker": ticker}, doc, upsert=True)
```

Full-document replace keyed on `ticker`. Safe here — unlike `price_history`, this collection has
exactly one writer (research.md R11).

### Refresh trigger

Runs after the per-ticker prefetch that populates `price_history` / `financials_cache`, so
signals never lag their inputs by a cycle. Also exposed as an admin job (`screener_refresh`)
through the existing `work_queue` mechanism — reusing `work_queue` rather than adding a
scheduler keeps Principle V satisfied.

Cost is bounded and predictable: the full 556-document universe computes in well under a second
today (research.md R4); ~8,340 documents at 15x remains a sub-minute batch.

---

## Consumer contract

The backend **reads only** and must tolerate:

| Condition | Required handling |
|---|---|
| Collection missing / empty (worker never ran) | `200` with `degraded: true`, explanatory `note` — never a 500 |
| `signals_as_of` older than one refresh cycle | serve with `degraded: true` |
| A field is `null` | treat as **unknown**, not as "does not match"; count it into `excluded_for_missing_data` (SC-008) |
| Ticker in `screener` but absent from `ticker_index` | valid — universe-only symbol; `is_tracked: false` |

The backend must **never** write to `screener`.

---

## Cross-service consistency (Principle VI)

`SCREENER = "screener"` is declared in **both** `backend/db.py` and `agent-runner/tools/db.py`.
Because the services share no package by design, the constant and the field vocabulary are
hand-synced, and drift is a bug rather than an acceptable seam.

Enforcement follows the precedent set by `price_store.py`: a **shared field-name table
duplicated verbatim in both services' tests** (`backend/tests/test_screener_contract.py` and
`agent-runner/tests/test_screener.py`), so a rename on one side fails the other side's suite.

The semantic layer description in `backend/semantic/schema.py` must be generated from — or
asserted against — that same field table. A field present in the collection but absent from the
description is invisible to the model; a field described but not present produces queries that
silently match nothing. Both failure modes are caught by a test asserting the two sets are equal.

---

## Test obligations

**`agent-runner/tests/test_screener.py`** — exhaustive pure-function cases:
empty bars · 1 bar · exactly 24 vs 25 bars · flat series (zero stdev) · zero-width range ·
missing `financials` · single annual period (trend undefined) · `$numberLong` coercion ·
each `financials_trend` branch · NaN/None in bar fields.

**`backend/tests/test_screener_contract.py`** — mirrored field table; asserts the semantic-layer
description matches the collection's field set exactly.

**`backend/tests/test_query_guard.py`** — adversarial: `$out`, `$merge`, `$function`,
`$accumulator`, `$where`, unknown `$`-stages, non-`screener` collection targets, missing
`$limit`, `$limit` above the hard cap, deeply nested stage smuggling.

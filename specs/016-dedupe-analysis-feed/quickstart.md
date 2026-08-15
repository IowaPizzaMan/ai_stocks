# Quickstart: Validate Deduplicate Analysis Feed & Storage

## Prerequisites

- Docker Compose stack running (`docker compose up -d mongodb backend agent-runner frontend`)
  or the equivalent local dev processes per each service's README.
- A watchlist with at least one ticker (e.g. `AAPL`) already registered — see
  `scripts/seed_watchlist.py` if empty.

## 1. Storage keeps only the latest analysis per ticker (US2, SC-002)

```bash
# Trigger analysis for AAPL twice via the queue (UI "Run All"/enqueue, or directly):
python - <<'EOF'
from tools.db import get_db, WORK_QUEUE
from datetime import datetime, timezone
db = get_db()
db[WORK_QUEUE].insert_one({"ticker": "AAPL", "status": "pending", "created_at": datetime.now(timezone.utc)})
EOF
# wait for agent-runner to process it, then repeat once more, then:
python - <<'EOF'
from tools.db import get_db, ANALYSES
db = get_db()
print(db[ANALYSES].count_documents({"ticker": "AAPL"}))  # expect: 1
EOF
```

Expected: `1`, and the stored document's `timestamp`/`signal`/`conviction` match the second
(most recent) run's output — see `contracts/analysis_write_path.md`.

## 2. One feed card per ticker (US1, SC-001)

```bash
curl -s "http://localhost:8000/analysis/feed?page=1&page_size=20" | python -m json.tool
```

Expected: at most one entry for `AAPL` (or any ticker analyzed more than once). `total`
equals the number of distinct tickers with a stored analysis, not the number of runs
(FR-002). Repeat with `?signal=`, `?sector=`, `?conviction=`, `?ticker=` filters — still one
entry per matching ticker (FR-003).

## 3. Per-ticker lookup returns only the latest (FR-005)

```bash
curl -s "http://localhost:8000/analysis/AAPL" | python -m json.tool
```

Expected: a single JSON object (not an array) matching the most recent analysis — see
`contracts/analysis_ticker_endpoint.md`. In the frontend, `/stock/AAPL#ai-summary` shows only
the current analysis, with no history/timeline list.

## 4. Existing duplicates are cleaned up (US3, SC-003)

Seed a synthetic duplicate scenario, then run the cleanup:

```bash
python - <<'EOF'
from tools.db import get_db, ANALYSES
from datetime import datetime, timedelta, timezone
db = get_db()
now = datetime.now(timezone.utc)
for i in range(5):
    db[ANALYSES].insert_one({"ticker": "DUPTEST", "timestamp": now - timedelta(days=i),
                              "signal": "neutral", "conviction": "low", "summary": f"run {i}"})
EOF

python scripts/dedupe_analyses.py

python - <<'EOF'
from tools.db import get_db, ANALYSES
db = get_db()
docs = list(db[ANALYSES].find({"ticker": "DUPTEST"}))
print(len(docs), docs[0]["summary"] if docs else None)  # expect: 1 "run 0" (the newest timestamp)
EOF

# Re-run — must be a no-op (FR-007):
python scripts/dedupe_analyses.py
```

Expected: after the first run, exactly one `DUPTEST` document remains (`summary == "run 0"`,
the latest timestamp). The second run reports zero documents removed.

## 5. Cross-check: total analyses == distinct tickers ever analyzed (SC-003)

```bash
python - <<'EOF'
from tools.db import get_db, ANALYSES
db = get_db()
total = db[ANALYSES].count_documents({})
distinct = len(db[ANALYSES].distinct("ticker"))
print(total, distinct, total == distinct)  # expect: True
EOF
```

## Automated coverage

Run the full suite instead of manual steps above where possible:

```bash
cd backend && pytest tests/test_routers.py -k "feed or ticker_history" -v
cd agent-runner && pytest tests/test_queue_worker.py -v
cd agent-runner && pytest tests/test_dedupe_analyses.py -v   # new, see contracts/dedupe_analyses_script.md
```

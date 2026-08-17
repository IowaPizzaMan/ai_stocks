"""Router tests against mongomock via dependency override."""
from datetime import datetime, timedelta, timezone

from db import (
    ANALYSES,
    BENEFICIAL_OWNERSHIP_CACHE,
    EARNINGS_CACHE,
    FINANCIALS_CACHE,
    INSTITUTIONAL_CACHE,
    STOCK_NEWS_CACHE,
    TICKER_INDEX,
    TRANSCRIPTS_CACHE,
    WATCHLIST,
    WORK_QUEUE,
)


def analysis_doc(ticker, ts, signal="bullish", conviction="high", sector=None):
    return {
        "ticker": ticker, "timestamp": ts, "signal": signal, "conviction": conviction,
        "summary": f"{ticker} looks {signal}", "key_trends": [], "flags": [],
        "sector": sector,
        "position_management": {"stair_step_stops": [1.0]},
        "sub_reports": {"technical": {"overall_technical_signal": signal}},
    }


NOW = datetime.now(timezone.utc)


# --- analysis ----------------------------------------------------------------

def test_feed_pagination_and_projection(client, db):
    for i in range(25):
        db[ANALYSES].insert_one(analysis_doc(f"T{i:02d}", NOW - timedelta(hours=i)))

    r = client.get("/analysis/feed").json()
    assert r["total"] == 25
    assert len(r["items"]) == 20
    assert r["items"][0]["ticker"] == "T00"  # newest first
    assert "sub_reports" not in r["items"][0]

    page2 = client.get("/analysis/feed?page=2").json()
    assert len(page2["items"]) == 5


def test_feed_filters(client, db):
    db[ANALYSES].insert_one(analysis_doc("AAA", NOW, signal="bullish"))
    db[ANALYSES].insert_one(analysis_doc("BBB", NOW, signal="bearish"))

    items = client.get("/analysis/feed?signal=bearish").json()["items"]
    assert [i["ticker"] for i in items] == ["BBB"]


def test_feed_ticker_filter_substring_case_insensitive(client, db):
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW))
    db[ANALYSES].insert_one(analysis_doc("APP", NOW))
    db[ANALYSES].insert_one(analysis_doc("MSFT", NOW))

    items = client.get("/analysis/feed?ticker=ap").json()["items"]
    assert sorted(i["ticker"] for i in items) == ["AAPL", "APP"]

    # regex metacharacters in input must be escaped, not interpreted
    assert client.get("/analysis/feed?ticker=A.P").json()["items"] == []


def test_feed_shows_one_card_after_reanalysis(client, db):
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW - timedelta(days=1),
                                          signal="bearish", conviction="low"))
    # simulates the write-path upsert (agent-runner/queue_worker.py) replacing
    # the ticker's prior record with a newer analysis
    db[ANALYSES].replace_one(
        {"ticker": "AAPL"},
        analysis_doc("AAPL", NOW, signal="bullish", conviction="high"),
        upsert=True,
    )

    r = client.get("/analysis/feed").json()
    aapl_items = [i for i in r["items"] if i["ticker"] == "AAPL"]
    assert len(aapl_items) == 1
    assert aapl_items[0]["signal"] == "bullish"
    assert aapl_items[0]["conviction"] == "high"


def test_feed_total_reflects_distinct_tickers_not_run_count(client, db):
    for i in range(25):
        db[ANALYSES].insert_one(analysis_doc(f"T{i:02d}", NOW - timedelta(hours=i)))
    # an extra historical record for an already-represented ticker must not
    # inflate the distinct-ticker total
    db[ANALYSES].replace_one(
        {"ticker": "T00"},
        analysis_doc("T00", NOW),
        upsert=True,
    )

    r = client.get("/analysis/feed").json()
    assert r["total"] == 25


def test_feed_filters_match_latest_value_per_ticker(client, db):
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW - timedelta(days=1), signal="bearish"))
    db[ANALYSES].replace_one(
        {"ticker": "AAPL"},
        analysis_doc("AAPL", NOW, signal="bullish"),
        upsert=True,
    )

    assert [i["ticker"] for i in client.get("/analysis/feed?signal=bullish").json()["items"]] == ["AAPL"]
    assert client.get("/analysis/feed?signal=bearish").json()["items"] == []


def test_ticker_analysis_returns_single_latest_object(client, db):
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW))
    db[ANALYSES].insert_one(analysis_doc("MSFT", NOW))

    r = client.get("/analysis/aapl").json()
    assert r["ticker"] == "AAPL"
    assert r["sub_reports"]  # full doc includes sub_reports


def test_ticker_analysis_unknown_ticker_returns_null(client, db):
    assert client.get("/analysis/zzzz").json() is None


def test_sector_endpoint_latest_per_ticker(client, db):
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW - timedelta(days=2), signal="bearish", sector="Technology"))
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW, signal="bullish", sector="Technology"))

    r = client.get("/analysis/sector/Technology").json()
    assert len(r) == 1
    assert r[0]["signal"] == "bullish"


# --- queue -------------------------------------------------------------------

def test_enqueue_registers_and_creates_job(client, db):
    r = client.post("/queue/nvda").json()
    assert r["status"] == "enqueued"
    assert db[WORK_QUEUE].find_one({"ticker": "NVDA"})["status"] == "pending"
    reg = db[TICKER_INDEX].find_one({"ticker": "NVDA"})
    assert reg["status"] == "active" and "manual" in reg["sources"]


def test_enqueue_idempotent(client, db):
    first = client.post("/queue/NVDA").json()
    second = client.post("/queue/NVDA").json()
    assert second["status"] == "already_queued"
    assert second["job_id"] == first["job_id"]
    assert db[WORK_QUEUE].count_documents({"ticker": "NVDA"}) == 1


def test_enqueue_reactivates_removed_ticker(client, db):
    db[TICKER_INDEX].insert_one({"ticker": "GONE", "status": "removed_from_market",
                                 "delisted_at": NOW, "delisted_reason": "x", "sources": []})
    client.post("/queue/GONE")
    reg = db[TICKER_INDEX].find_one({"ticker": "GONE"})
    assert reg["status"] == "active"
    assert "delisted_at" not in reg


def test_run_all_sweeps_active_only(client, db):
    for t, status in [("AAA", "active"), ("BBB", "active"), ("CCC", "disabled"),
                      ("DDD", "removed_from_market")]:
        db[TICKER_INDEX].insert_one({"ticker": t, "status": status, "sources": []})
    db[WORK_QUEUE].insert_one({"ticker": "BBB", "status": "pending", "created_at": NOW,
                               "updated_at": NOW})

    r = client.post("/queue/all").json()
    assert r["enqueued"] == ["AAA"]
    assert r["already_queued"] == ["BBB"]
    assert r["universe_size"] == 2


def test_queue_status(client, db):
    db[WORK_QUEUE].insert_one({"ticker": "AAA", "status": "pending", "created_at": NOW, "updated_at": NOW})
    db[WORK_QUEUE].insert_one({"ticker": "BBB", "status": "running", "created_at": NOW, "updated_at": NOW})
    db[WORK_QUEUE].insert_one({"ticker": "CCC", "status": "done", "created_at": NOW, "updated_at": NOW})

    r = client.get("/queue").json()
    assert r["pending_count"] == 1 and r["running_count"] == 1
    assert r["pending"][0]["ticker"] == "AAA"


# --- pull mode / full refresh (024 US5) --------------------------------------

def test_enqueue_defaults_to_delta(client, db):
    r = client.post("/queue/NVDA").json()
    assert r["mode"] == "delta"
    assert db[WORK_QUEUE].find_one({"ticker": "NVDA"})["mode"] == "delta"


def test_enqueue_full_mode_is_persisted_and_echoed(client, db):
    r = client.post("/queue/NVDA?mode=full").json()
    assert r["status"] == "enqueued"
    assert r["mode"] == "full"
    assert db[WORK_QUEUE].find_one({"ticker": "NVDA"})["mode"] == "full"


def test_unknown_mode_is_422_not_a_silent_delta(client, db):
    """Being quietly given a delta pull when you asked for a full refresh is
    precisely the failure this control exists to prevent."""
    assert client.post("/queue/NVDA?mode=deep").status_code == 422
    assert db[WORK_QUEUE].count_documents({}) == 0


def test_full_request_upgrades_a_pending_delta_job(client, db):
    """research D8 — answering 'already_queued' here would tell the operator
    their refresh was handled and then hand them a delta pull."""
    first = client.post("/queue/NVDA").json()
    second = client.post("/queue/NVDA?mode=full").json()

    assert second["status"] == "upgraded_to_full"
    assert second["mode"] == "full"
    assert second["job_id"] == first["job_id"]
    assert db[WORK_QUEUE].count_documents({"ticker": "NVDA"}) == 1
    assert db[WORK_QUEUE].find_one({"ticker": "NVDA"})["mode"] == "full"


def test_full_request_while_running_reports_rather_than_upgrading(client, db):
    """Too late to upgrade a job already in flight — say so instead of implying
    the refresh is underway."""
    db[WORK_QUEUE].insert_one({"ticker": "NVDA", "status": "running", "mode": "delta",
                               "created_at": NOW, "updated_at": NOW})
    r = client.post("/queue/NVDA?mode=full").json()

    assert r["status"] == "already_queued"
    assert r["mode"] == "delta"
    assert db[WORK_QUEUE].find_one({"ticker": "NVDA"})["mode"] == "delta"


def test_delta_request_does_not_downgrade_a_pending_full_job(client, db):
    """The reverse of the upgrade rule — a routine pull must not quietly cancel
    a full refresh the operator asked for."""
    client.post("/queue/NVDA?mode=full")
    r = client.post("/queue/NVDA").json()

    assert r["status"] == "already_queued"
    assert r["mode"] == "full"
    assert db[WORK_QUEUE].find_one({"ticker": "NVDA"})["mode"] == "full"


def test_full_refresh_works_for_a_ticker_with_no_stored_data(client, db):
    """FR-029 — with no baseline it simply behaves as a first-ever pull."""
    r = client.post("/queue/BRAND-NEW?mode=full")
    assert r.status_code == 200
    assert r.json()["mode"] == "full"


def test_queue_status_reports_mode_and_defaults_legacy_jobs_to_delta(client, db):
    db[WORK_QUEUE].insert_one({"ticker": "AAA", "status": "pending", "mode": "full",
                               "created_at": NOW, "updated_at": NOW})
    # queued before 024 shipped — no mode field at all (FR-021)
    db[WORK_QUEUE].insert_one({"ticker": "BBB", "status": "running",
                               "created_at": NOW, "updated_at": NOW})

    r = client.get("/queue").json()
    assert r["pending"][0]["mode"] == "full"
    assert r["running"][0]["mode"] == "delta"


def test_run_all_stays_delta_only(client, db):
    """Bulk full refresh is explicitly out of scope (spec, Out of Scope)."""
    db[TICKER_INDEX].insert_one({"ticker": "AAA", "status": "active", "sources": []})
    client.post("/queue/all?mode=full")
    assert db[WORK_QUEUE].find_one({"ticker": "AAA"})["mode"] == "delta"


# --- watchlist ---------------------------------------------------------------

def test_watchlist_add_get_remove(client, db):
    added = client.post("/watchlist/aapl", json={"name": "Apple", "sector": "Technology"}).json()
    assert added["ticker"] == "AAPL"

    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW))
    listed = client.get("/watchlist").json()
    assert listed["count"] == 1
    assert listed["items"][0]["last_signal"] == "bullish"
    assert db[TICKER_INDEX].find_one({"ticker": "AAPL"})["sources"] == ["watchlist"]

    assert client.post("/watchlist/AAPL").status_code == 409
    assert client.delete("/watchlist/AAPL").json() == {"removed": "AAPL"}
    assert client.delete("/watchlist/AAPL").status_code == 404


# --- stocks / tickers --------------------------------------------------------

def test_search_enriches_with_latest_signal(client, db):
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "name": "Apple Inc.", "status": "active"})
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW))

    r = client.get("/stocks/search?q=aa").json()
    assert r[0]["ticker"] == "AAPL"
    assert r[0]["signal"] == "bullish"


def test_get_ticker_record_and_404(client, db):
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "name": "Apple Inc.", "status": "active"})
    assert client.get("/stocks/AAPL").json()["name"] == "Apple Inc."
    assert client.get("/stocks/ZZZZ").status_code == 404


def test_financials_endpoint(client, db):
    db[FINANCIALS_CACHE].insert_one({"ticker": "AAPL", "data": {"income_annual": [{"revenue": 1}]},
                                     "fetched_at": NOW})
    assert client.get("/stocks/AAPL/financials").json()["income_annual"] == [{"revenue": 1}]
    assert client.get("/stocks/MSFT/financials").status_code == 404


def test_signals_endpoint(client, db):
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW))
    r = client.get("/stocks/AAPL/signals").json()
    assert r["ticker"] == "AAPL"
    assert r["technical"]["overall_technical_signal"] == "bullish"
    assert client.get("/stocks/MSFT/signals").status_code == 404


# --- pull metrics (024 US1) ---------------------------------------------------

def pull_doc(ticker, started, total_ms=1000, stages=None, mode="delta", outcome="done"):
    return {
        "ticker": ticker, "job_id": "j1", "mode": mode,
        "started_at": started, "completed_at": started + timedelta(seconds=1),
        "total_ms": total_ms, "outcome": outcome,
        "stages": stages if stages is not None else [
            {"name": "news", "elapsed_ms": 100, "requests": 3, "bytes": 900,
             "retrieval": "incremental", "outcome": "fetched"},
            {"name": "price", "elapsed_ms": 500, "requests": 1, "bytes": 4000,
             "retrieval": "full", "outcome": "fetched"},
            {"name": "indicators", "elapsed_ms": 20, "requests": 0, "bytes": 0,
             "retrieval": "stored", "outcome": "stored"},
        ],
    }


def test_pull_metrics_sorts_stages_most_expensive_first(client, db):
    """SC-006 — the operator reads the top three without re-sorting them."""
    db["pull_metrics"].insert_one(pull_doc("AAPL", NOW))
    r = client.get("/stocks/AAPL/pull-metrics").json()

    names = [s["name"] for s in r["pulls"][0]["stages"]]
    assert names == ["price", "news", "indicators"]


def test_pull_metrics_surfaces_unaccounted_time(client, db):
    """FR-004 — time the breakdown cannot explain is itself a finding, so it is
    reported rather than quietly dropped."""
    db["pull_metrics"].insert_one(pull_doc("AAPL", NOW, total_ms=1000))
    pull = client.get("/stocks/AAPL/pull-metrics").json()["pulls"][0]

    assert pull["accounted_ms"] == 620          # 500 + 100 + 20
    assert pull["unaccounted_ms"] == 380
    assert pull["total_ms"] == 1000


def test_pull_metrics_never_reports_negative_unaccounted_time(client, db):
    """A stage clock that overruns the pull clock is a bug, but it must not
    surface as a negative number in the UI."""
    db["pull_metrics"].insert_one(pull_doc("AAPL", NOW, total_ms=10))
    pull = client.get("/stocks/AAPL/pull-metrics").json()["pulls"][0]
    assert pull["unaccounted_ms"] == 0


def test_pull_metrics_defaults_to_the_latest_pull(client, db):
    db["pull_metrics"].insert_many([
        pull_doc("AAPL", NOW - timedelta(hours=2), total_ms=111),
        pull_doc("AAPL", NOW, total_ms=222),
    ])
    r = client.get("/stocks/AAPL/pull-metrics").json()
    assert len(r["pulls"]) == 1
    assert r["pulls"][0]["total_ms"] == 222


def test_pull_metrics_limit_is_honoured_and_clamped(client, db):
    db["pull_metrics"].insert_many([
        pull_doc("AAPL", NOW - timedelta(hours=i)) for i in range(25)
    ])
    assert len(client.get("/stocks/AAPL/pull-metrics?limit=5").json()["pulls"]) == 5
    assert len(client.get("/stocks/AAPL/pull-metrics?limit=999").json()["pulls"]) == 20


def test_pull_metrics_reports_mode_and_outcome(client, db):
    """FR-028 — the operator must be able to tell a full refresh from a delta
    pull, and a degraded run from a clean one."""
    db["pull_metrics"].insert_one(
        pull_doc("AAPL", NOW, mode="full", outcome="degraded"))
    pull = client.get("/stocks/AAPL/pull-metrics").json()["pulls"][0]
    assert pull["mode"] == "full"
    assert pull["outcome"] == "degraded"


def test_pull_metrics_404_when_ticker_never_pulled(client, db):
    assert client.get("/stocks/ZZZZ/pull-metrics").status_code == 404


def test_pull_metrics_is_case_insensitive(client, db):
    db["pull_metrics"].insert_one(pull_doc("AAPL", NOW))
    assert client.get("/stocks/aapl/pull-metrics").status_code == 200


def test_tickers_admin_list_patch_delete(client, db):
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "status": "active"})
    db[TICKER_INDEX].insert_one({"ticker": "MSFT", "status": "disabled"})
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW))
    db[WATCHLIST].insert_one({"ticker": "AAPL"})

    listed = client.get("/tickers").json()
    assert listed["total"] == 2 and listed["active_count"] == 1 and listed["disabled_count"] == 1

    patched = client.patch("/tickers/AAPL", json={"status": "disabled"}).json()
    assert patched["status"] == "disabled"

    deleted = client.delete("/tickers/AAPL").json()
    assert deleted == {"deleted": "AAPL"}
    assert db[ANALYSES].count_documents({"ticker": "AAPL"}) == 0
    assert db[WATCHLIST].count_documents({"ticker": "AAPL"}) == 0
    assert client.delete("/tickers/AAPL").status_code == 404


def test_delete_ticker_purges_all_scoped_collections(client, db):
    """specs/023-remove-stocks FR-009: deleting a ticker must clear every
    collection scoped to it, not just the original five — including
    earnings_cache, which mixes per-ticker "history" docs with market-wide
    "calendar"/"universe" docs that must survive (data-model.md)."""
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "status": "active"})
    db[TRANSCRIPTS_CACHE].insert_one({"ticker": "AAPL", "year": 2026, "quarter": 1, "text": "..."})
    db[STOCK_NEWS_CACHE].insert_one({"ticker": "AAPL", "articles": []})
    db[INSTITUTIONAL_CACHE].insert_one({"ticker": "AAPL", "data": {}})
    db[BENEFICIAL_OWNERSHIP_CACHE].insert_one({"ticker": "AAPL", "data": {}})
    db[EARNINGS_CACHE].insert_one({"type": "history", "ticker": "AAPL", "data": []})
    db[EARNINGS_CACHE].insert_one({"type": "calendar", "days": 30, "data": []})

    deleted = client.delete("/tickers/AAPL").json()
    assert deleted == {"deleted": "AAPL"}

    assert db[TRANSCRIPTS_CACHE].count_documents({"ticker": "AAPL"}) == 0
    assert db[STOCK_NEWS_CACHE].count_documents({"ticker": "AAPL"}) == 0
    assert db[INSTITUTIONAL_CACHE].count_documents({"ticker": "AAPL"}) == 0
    assert db[BENEFICIAL_OWNERSHIP_CACHE].count_documents({"ticker": "AAPL"}) == 0
    assert db[EARNINGS_CACHE].count_documents({"type": "history", "ticker": "AAPL"}) == 0
    # Market-wide earnings cache docs (no ticker) must NOT be swept up.
    assert db[EARNINGS_CACHE].count_documents({"type": "calendar"}) == 1


def test_bulk_add(client, db):
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "status": "disabled", "sources": []})
    r = client.post("/tickers/bulk", json={"tickers": "aapl msft,nvda\n123bad aapl"}).json()

    assert r["added"] == ["MSFT", "NVDA"]
    assert r["already_existed"] == ["AAPL"]
    assert r["invalid"] == ["123BAD"]
    assert db[TICKER_INDEX].find_one({"ticker": "AAPL"})["status"] == "active"

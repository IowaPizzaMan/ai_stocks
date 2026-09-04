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
    # 037-stocks-conviction-and-activity: sort is (conviction_rank desc, ticker
    # asc) now, not recency — every doc here shares the same conviction, so
    # this is really exercising the ticker-ascending tie-break (T00 sorts
    # first alphabetically among T00-T24). See test_analysis_feed_ordering.py
    # for dedicated conviction-ordering coverage.
    assert r["items"][0]["ticker"] == "T00"
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


def test_feed_sentiment_filter_returns_only_tagged_tickers(client, db):
    """specs/028-dashboard-tweaks-batch US3 FR-009."""
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW))
    db[ANALYSES].insert_one(analysis_doc("MSFT", NOW))
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "status": "active", "sentiment": "liked"})
    db[TICKER_INDEX].insert_one({"ticker": "MSFT", "status": "active"})

    items = client.get("/analysis/feed?sentiment=liked").json()["items"]
    assert [i["ticker"] for i in items] == ["AAPL"]


def test_feed_sentiment_filter_intersects_with_signal_filter(client, db):
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW, signal="bullish"))
    db[ANALYSES].insert_one(analysis_doc("MSFT", NOW, signal="bearish"))
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "status": "active", "sentiment": "liked"})
    db[TICKER_INDEX].insert_one({"ticker": "MSFT", "status": "active", "sentiment": "liked"})

    items = client.get("/analysis/feed?sentiment=liked&signal=bearish").json()["items"]
    assert [i["ticker"] for i in items] == ["MSFT"]


def test_feed_sentiment_filter_empty_tagged_set_returns_nothing_not_everything(client, db):
    """The one way this filter fails dangerously — an empty tagged set must
    never silently fall back to the unfiltered feed."""
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW))
    db[ANALYSES].insert_one(analysis_doc("MSFT", NOW))

    r = client.get("/analysis/feed?sentiment=liked").json()
    assert r["items"] == []
    assert r["total"] == 0


def test_feed_sentiment_filter_disliked(client, db):
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW))
    db[ANALYSES].insert_one(analysis_doc("MSFT", NOW))
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "status": "active", "sentiment": "disliked"})
    db[TICKER_INDEX].insert_one({"ticker": "MSFT", "status": "active", "sentiment": "liked"})

    items = client.get("/analysis/feed?sentiment=disliked").json()["items"]
    assert [i["ticker"] for i in items] == ["AAPL"]


def test_feed_items_carry_name_and_logo_url_from_ticker_index(client, db):
    """specs/029-company-profile-tweaks US3 (FR-021a) — one ticker_index
    query per page, attached to each item; a ticker with no profile yet
    still returns null fields rather than omitting the keys."""
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW))
    db[ANALYSES].insert_one(analysis_doc("MSFT", NOW))
    db[TICKER_INDEX].insert_one({
        "ticker": "AAPL", "status": "active", "name": "Apple Inc.",
        "logo_url": "https://images.financialmodelingprep.com/symbol/AAPL.png",
    })
    db[TICKER_INDEX].insert_one({"ticker": "MSFT", "status": "active"})

    items = {i["ticker"]: i for i in client.get("/analysis/feed").json()["items"]}
    assert items["AAPL"]["name"] == "Apple Inc."
    assert items["AAPL"]["logo_url"] == "https://images.financialmodelingprep.com/symbol/AAPL.png"
    assert items["MSFT"]["name"] is None
    assert items["MSFT"]["logo_url"] is None


def test_feed_items_query_ticker_index_once_per_page_not_per_item(client, db, monkeypatch):
    for i in range(5):
        db[ANALYSES].insert_one(analysis_doc(f"T{i:02d}", NOW - timedelta(hours=i)))
        db[TICKER_INDEX].insert_one({"ticker": f"T{i:02d}", "status": "active"})

    calls = []
    real_find = db[TICKER_INDEX].find

    def counting_find(*args, **kwargs):
        calls.append((args, kwargs))
        return real_find(*args, **kwargs)

    monkeypatch.setattr(db[TICKER_INDEX], "find", counting_find)

    client.get("/analysis/feed")
    assert len(calls) == 1  # not one per item


def test_feed_industry_filter_narrows(client, db):
    """specs/029-company-profile-tweaks US5 (FR-024/FR-025)."""
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW))
    db[ANALYSES].insert_one(analysis_doc("GOOGL", NOW))
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "status": "active", "industry": "Consumer Electronics"})
    db[TICKER_INDEX].insert_one({"ticker": "GOOGL", "status": "active", "industry": "Internet Content & Information"})

    items = client.get("/analysis/feed?industry=Consumer Electronics").json()["items"]
    assert [i["ticker"] for i in items] == ["AAPL"]


def test_feed_industry_filter_no_match_returns_empty_not_unfiltered(client, db):
    """The 028 invariant, extended to industry: an empty resolved ticker set
    must yield $in: [] and never be silently skipped."""
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW))
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "status": "active", "industry": "Consumer Electronics"})

    r = client.get("/analysis/feed?industry=NoSuchIndustry").json()
    assert r["items"] == []
    assert r["total"] == 0


def test_feed_industry_filter_combines_with_signal_as_and(client, db):
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW, signal="bullish"))
    db[ANALYSES].insert_one(analysis_doc("MSFT", NOW, signal="bearish"))
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "status": "active", "industry": "Consumer Electronics"})
    db[TICKER_INDEX].insert_one({"ticker": "MSFT", "status": "active", "industry": "Consumer Electronics"})

    items = client.get("/analysis/feed?industry=Consumer Electronics&signal=bearish").json()["items"]
    assert [i["ticker"] for i in items] == ["MSFT"]


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
    """specs/029-company-profile-tweaks (FR-026) — sector is resolved from
    ticker_index, not analyses.sector."""
    db[TICKER_INDEX].insert_one({"ticker": "AAPL", "status": "active", "sector": "Technology"})
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW - timedelta(days=2), signal="bearish"))
    db[ANALYSES].insert_one(analysis_doc("AAPL", NOW, signal="bullish"))

    r = client.get("/analysis/sector/Technology").json()
    assert len(r) == 1
    assert r[0]["signal"] == "bullish"


def test_sector_endpoint_unknown_sector_returns_empty(client, db):
    assert client.get("/analysis/sector/NoSuchSector").json() == []


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

"""GET /portfolio/digest + POST /portfolio/digest/regenerate — specs/027.

Cross-stock AI summary panel on the Stocks page. The endpoint only ever reads
a singleton `portfolio_digest_cache` document and derives staleness from it;
the regenerate endpoint only ever enqueues a non-ticker work_queue job — the
LLM synthesis itself lives in agent-runner (tested separately).
"""
from datetime import datetime, timedelta, timezone

from db import PORTFOLIO_DIGEST_CACHE, WORK_QUEUE


def _utcnow():
    return datetime.now(timezone.utc)


# --- GET /portfolio/digest ----------------------------------------------------


def test_no_document_yet_returns_the_empty_state(client, db):
    body = client.get("/portfolio/digest").json()

    assert body == {
        "as_of": None,
        "overview": None,
        "highlights": [],
        "stock_count": 0,
        "total_tracked_count": 0,
        "capped": False,
        "stale": False,
    }


def test_document_with_only_success_fields_is_not_stale(client, db):
    db[PORTFOLIO_DIGEST_CACHE].insert_one({
        "generated_at": _utcnow(),
        "overview": "All quiet.",
        "highlights": [{"ticker": "AAPL", "signal": "bullish", "conviction": "high", "note": "n"}],
        "stock_count": 1,
        "total_tracked_count": 1,
        "capped": False,
    })

    body = client.get("/portfolio/digest").json()

    assert body["overview"] == "All quiet."
    assert body["stock_count"] == 1
    assert body["highlights"][0]["ticker"] == "AAPL"
    assert body["stale"] is False


def test_error_newer_than_the_last_success_marks_it_stale(client, db):
    generated_at = _utcnow() - timedelta(hours=2)
    db[PORTFOLIO_DIGEST_CACHE].insert_one({
        "generated_at": generated_at,
        "overview": "Old but good.",
        "highlights": [],
        "stock_count": 3,
        "total_tracked_count": 3,
        "capped": False,
        "last_error": "ollama: connection refused",
        "last_error_at": generated_at + timedelta(hours=1),
    })

    body = client.get("/portfolio/digest").json()

    assert body["overview"] == "Old but good."  # last-good content still served
    assert body["stale"] is True


def test_error_older_than_the_last_success_is_not_stale(client, db):
    generated_at = _utcnow()
    db[PORTFOLIO_DIGEST_CACHE].insert_one({
        "generated_at": generated_at,
        "overview": "Fixed since.",
        "highlights": [],
        "stock_count": 2,
        "total_tracked_count": 2,
        "capped": False,
        "last_error": "a since-resolved failure",
        "last_error_at": generated_at - timedelta(hours=1),
    })

    body = client.get("/portfolio/digest").json()

    assert body["stale"] is False


def test_capped_flag_and_total_tracked_count_pass_through(client, db):
    db[PORTFOLIO_DIGEST_CACHE].insert_one({
        "generated_at": _utcnow(),
        "overview": "Top 25 shown.",
        "highlights": [],
        "stock_count": 25,
        "total_tracked_count": 40,
        "capped": True,
    })

    body = client.get("/portfolio/digest").json()

    assert body["capped"] is True
    assert body["stock_count"] == 25
    assert body["total_tracked_count"] == 40


# --- POST /portfolio/digest/regenerate ----------------------------------------


def test_regenerate_enqueues_a_non_ticker_admin_job(client, db):
    body = client.post("/portfolio/digest/regenerate").json()

    assert body["status"] == "enqueued"
    job = db[WORK_QUEUE].find_one({"job_type": "portfolio_digest"})
    assert job is not None
    assert "ticker" not in job
    assert job["status"] == "pending"
    assert str(job["_id"]) == body["job_id"]


def test_regenerate_while_one_is_pending_is_deduped(client, db):
    first = client.post("/portfolio/digest/regenerate").json()

    second = client.post("/portfolio/digest/regenerate").json()

    assert second["status"] == "already_queued"
    assert second["job_id"] == first["job_id"]
    assert db[WORK_QUEUE].count_documents({"job_type": "portfolio_digest"}) == 1


def test_regenerate_while_one_is_running_is_also_deduped(client, db):
    first = client.post("/portfolio/digest/regenerate").json()
    db[WORK_QUEUE].update_one({"job_type": "portfolio_digest"}, {"$set": {"status": "running"}})

    second = client.post("/portfolio/digest/regenerate").json()

    assert second["status"] == "already_queued"
    assert second["job_id"] == first["job_id"]


def test_regenerate_after_the_previous_job_finished_enqueues_a_new_one(client, db):
    first = client.post("/portfolio/digest/regenerate").json()
    db[WORK_QUEUE].update_one({"job_type": "portfolio_digest"}, {"$set": {"status": "done"}})

    second = client.post("/portfolio/digest/regenerate").json()

    assert second["status"] == "enqueued"
    assert second["job_id"] != first["job_id"]
    assert db[WORK_QUEUE].count_documents({"job_type": "portfolio_digest"}) == 2

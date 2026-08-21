"""Contract tests for the economics dashboard endpoints.
Spec: specs/026-macro-market-dashboard/contracts/macro-api.md
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from db import (
    DATASET_META,
    ECONOMIC_CALENDAR_EVENTS,
    ECONOMIC_INDICATORS,
    MARKET_RISK_PREMIUM,
    TREASURY_RATES,
)


def treasury_row(d: str, **maturities) -> dict:
    row = {"date": d, "source": "fmp"}
    row.update(maturities)
    return row


def set_economics_freshness(db, status: str, when: datetime | None = None) -> None:
    """Mirrors agent-runner's write_dataset_meta contract exactly: a partial
    $set, so a "failed" write never wipes a prior success's last_success_at."""
    update = {"$set": {"last_run_status": status, "source": "fmp"}}
    if status == "success":
        update["$set"]["last_success_at"] = when or datetime.now(timezone.utc)
        update["$set"]["record_count"] = 10
    db[DATASET_META].update_one({"dataset": "economics"}, update, upsert=True)


class TestTreasuryCurve:
    def test_empty_collection_returns_200_with_null_session(self, client, db):
        r = client.get("/market/treasury-curve")
        assert r.status_code == 200
        body = r.json()
        assert body["session"] is None
        assert body["curve"] == []
        assert body["comparison_sessions"] == {"month_ago": None, "year_ago": None}
        assert [s["key"] for s in body["spreads"]] == ["10y-2y", "30y-10y", "10y-3m"]
        assert all(s["current_bps"] is None for s in body["spreads"])
        assert body["as_of"] is None
        assert body["stale"] is False

    def test_curve_covers_every_maturity_ordered_by_months(self, client, db):
        db[TREASURY_RATES].insert_one(treasury_row(
            "2026-08-19", m1=3.77, m2=3.81, m3=3.86, m6=3.94,
            y1=4.0, y2=4.19, y3=4.25, y5=4.35, y7=4.48, y10=4.65, y20=5.17, y30=5.19,
        ))
        set_economics_freshness(db, "success")

        body = client.get("/market/treasury-curve").json()
        curve = body["curve"]
        assert [p["maturity"] for p in curve] == [
            "1M", "2M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y",
        ]
        assert [p["months"] for p in curve] == sorted(p["months"] for p in curve)
        assert curve[0]["current"] == 3.77  # 1M
        assert curve[-1]["current"] == 5.19  # 30Y

    def test_missing_maturity_is_null_not_zero(self, client, db):
        db[TREASURY_RATES].insert_one(treasury_row("2026-08-19", y10=4.65))  # m1 absent
        set_economics_freshness(db, "success")

        curve = client.get("/market/treasury-curve").json()["curve"]
        one_month = next(p for p in curve if p["maturity"] == "1M")
        assert one_month["current"] is None

    def test_spreads_always_present_even_when_a_maturity_is_missing(self, client, db):
        db[TREASURY_RATES].insert_one(treasury_row("2026-08-19", y10=4.65))  # no y2, no m3
        set_economics_freshness(db, "success")

        spreads = {s["key"]: s for s in client.get("/market/treasury-curve").json()["spreads"]}
        assert set(spreads) == {"10y-2y", "30y-10y", "10y-3m"}
        assert spreads["10y-2y"]["current_bps"] is None  # y2 missing
        assert spreads["30y-10y"]["current_bps"] is None  # y30 missing

    def test_negative_spread_is_inverted_exactly_zero_is_not(self, client, db):
        db[TREASURY_RATES].insert_many([
            treasury_row("2026-08-18", y10=4.00, y2=4.00),  # 0 bps — not inverted
            treasury_row("2026-08-19", y10=4.00, y2=4.20),  # -20 bps — inverted
        ])
        set_economics_freshness(db, "success")

        spreads = {s["key"]: s for s in client.get("/market/treasury-curve").json()["spreads"]}
        assert spreads["10y-2y"]["current_bps"] == -20.0
        assert spreads["10y-2y"]["inverted"] is True

    def test_change_bps_compares_against_previous_stored_session_across_a_gap(self, client, db):
        # Friday -> Monday: no Saturday/Sunday rows at all (weekend gap)
        db[TREASURY_RATES].insert_many([
            treasury_row("2026-08-14", y10=4.60, y2=4.10),  # Friday: 50 bps
            treasury_row("2026-08-17", y10=4.65, y2=4.19),  # Monday: 46 bps
        ])
        set_economics_freshness(db, "success")

        spreads = {s["key"]: s for s in client.get("/market/treasury-curve").json()["spreads"]}
        assert spreads["10y-2y"]["current_bps"] == 46.0
        assert spreads["10y-2y"]["change_bps"] == -4.0  # 46 - 50, vs the prior *stored* row

    def test_change_bps_skips_a_session_missing_the_spread_maturities(self, client, db):
        db[TREASURY_RATES].insert_many([
            treasury_row("2026-08-13", y10=4.60, y2=4.10),  # 50 bps
            treasury_row("2026-08-14", y10=4.61),  # y2 missing — dropped from this spread's series
            treasury_row("2026-08-17", y10=4.65, y2=4.19),  # 46 bps
        ])
        set_economics_freshness(db, "success")

        spreads = {s["key"]: s for s in client.get("/market/treasury-curve").json()["spreads"]}
        # change is against 08-13 (the last session with both legs), not the null 08-14 row
        assert spreads["10y-2y"]["change_bps"] == -4.0

    def test_year_ago_overlay_absent_when_history_does_not_reach_back(self, client, db):
        db[TREASURY_RATES].insert_one(treasury_row("2026-08-19", y10=4.65))
        set_economics_freshness(db, "success")

        body = client.get("/market/treasury-curve").json()
        assert body["comparison_sessions"]["year_ago"] is None
        ten_year = next(p for p in body["curve"] if p["maturity"] == "10Y")
        assert ten_year["year_ago"] is None

    def test_month_ago_overlay_present_when_history_reaches_back(self, client, db):
        db[TREASURY_RATES].insert_many([
            treasury_row("2026-07-20", y10=4.50),
            treasury_row("2026-08-19", y10=4.65),
        ])
        set_economics_freshness(db, "success")

        body = client.get("/market/treasury-curve").json()
        assert body["comparison_sessions"]["month_ago"] == "2026-07-20"
        ten_year = next(p for p in body["curve"] if p["maturity"] == "10Y")
        assert ten_year["month_ago"] == 4.50

    def test_stale_flag_reflects_a_failed_last_run(self, client, db):
        db[TREASURY_RATES].insert_one(treasury_row("2026-08-19", y10=4.65))
        set_economics_freshness(db, "success", when=datetime(2026, 8, 18, tzinfo=timezone.utc))
        set_economics_freshness(db, "failed")  # most recent run failed

        body = client.get("/market/treasury-curve").json()
        assert body["stale"] is True
        assert body["as_of"] == "2026-08-18T00:00:00+00:00"  # last_success_at doesn't regress

    def test_lookback_days_bounds_only_the_spread_series_not_the_curve(self, client, db):
        # Treasury data is dense (~daily), so bounding the trend series by
        # entry count is equivalent to bounding it by day count in practice —
        # 40 consecutive daily rows, plus one far outside the 30-day window.
        old = (datetime(2026, 8, 19) - timedelta(days=500)).strftime("%Y-%m-%d")
        rows = [treasury_row(old, y10=4.10, y2=3.80)]
        base = datetime(2026, 7, 11)
        for i in range(40):
            d = (base + timedelta(days=i)).strftime("%Y-%m-%d")
            rows.append(treasury_row(d, y10=4.60 + i * 0.001, y2=4.10 + i * 0.001))
        db[TREASURY_RATES].insert_many(rows)
        set_economics_freshness(db, "success")

        body = client.get("/market/treasury-curve?lookback_days=30").json()
        spread = next(s for s in body["spreads"] if s["key"] == "10y-2y")
        assert len(spread["series"]) == 30  # bounded to the last 30 sessions
        assert spread["series"][0]["date"] != old  # the 500-day-old point is excluded
        assert spread["current_bps"] is not None  # but current/change still reflect full history


def calendar_event(when: datetime, event: str = "Retail Sales MoM", **overrides) -> dict:
    row = {
        "date": when, "event": event, "country": "US", "currency": "USD",
        "impact": "High", "previous": 0.4, "estimate": 0.3, "actual": None, "unit": "%",
        "source": "fmp", "collected_at": datetime.now(timezone.utc),
    }
    row.update(overrides)
    return row


class TestEconomicCalendar:
    def test_empty_window_returns_200_with_empty_lists(self, client, db):
        r = client.get("/market/economic-calendar")
        assert r.status_code == 200
        body = r.json()
        assert body["upcoming"] == []
        assert body["reported"] == []
        assert body["timezone"] == "America/New_York"

    def test_event_later_today_lands_in_upcoming_not_dropped_as_past(self, client, db):
        now = datetime.now(timezone.utc)
        later_today = now + timedelta(hours=2)
        db[ECONOMIC_CALENDAR_EVENTS].insert_one(calendar_event(later_today, "Later Today Release"))

        body = client.get("/market/economic-calendar").json()
        assert [e["event"] for e in body["upcoming"]] == ["Later Today Release"]
        assert body["reported"] == []

    def test_event_is_reported_only_once_actual_is_present(self, client, db):
        now = datetime.now(timezone.utc)
        db[ECONOMIC_CALENDAR_EVENTS].insert_many([
            calendar_event(now + timedelta(days=1), "Not Yet Reported", actual=None),
            calendar_event(now - timedelta(days=1), "Already Reported", actual=0.6),
        ])

        body = client.get("/market/economic-calendar").json()
        assert [e["event"] for e in body["upcoming"]] == ["Not Yet Reported"]
        assert [e["event"] for e in body["reported"]] == ["Already Reported"]

    def test_past_event_with_no_actual_appears_in_neither_list(self, client, db):
        now = datetime.now(timezone.utc)
        db[ECONOMIC_CALENDAR_EVENTS].insert_one(
            calendar_event(now - timedelta(hours=1), "Data Lag", actual=None)
        )

        body = client.get("/market/economic-calendar").json()
        assert body["upcoming"] == []
        assert body["reported"] == []

    def test_comparison_is_null_not_in_line_when_no_estimate_published(self, client, db):
        now = datetime.now(timezone.utc)
        db[ECONOMIC_CALENDAR_EVENTS].insert_one(
            calendar_event(now - timedelta(days=1), "No Estimate", estimate=None, actual=0.5)
        )

        reported = client.get("/market/economic-calendar").json()["reported"]
        assert reported[0]["comparison"] is None
        assert reported[0]["actual"] == 0.5

    def test_comparison_labels_above_below_and_in_line_mechanically(self, client, db):
        now = datetime.now(timezone.utc)
        db[ECONOMIC_CALENDAR_EVENTS].insert_many([
            calendar_event(now - timedelta(days=1), "Beat", estimate=0.3, actual=0.6),
            calendar_event(now - timedelta(days=2), "Miss", estimate=0.3, actual=0.1),
            calendar_event(now - timedelta(days=3), "Exact", estimate=0.3, actual=0.3),
        ])

        reported = {e["event"]: e for e in client.get("/market/economic-calendar").json()["reported"]}
        assert reported["Beat"]["comparison"] == "above"
        assert reported["Beat"]["surprise"] == pytest.approx(0.3)
        assert reported["Miss"]["comparison"] == "below"
        assert reported["Exact"]["comparison"] == "in_line"
        assert reported["Exact"]["surprise"] == 0.0

    def test_response_never_asserts_market_direction_or_polarity(self, client, db):
        now = datetime.now(timezone.utc)
        db[ECONOMIC_CALENDAR_EVENTS].insert_one(
            calendar_event(now - timedelta(days=1), "Hot CPI", estimate=0.3, actual=0.9)
        )

        body = client.get("/market/economic-calendar").json()
        payload = json.dumps(body).lower()
        for banned in ("bullish", "bearish", "positive", "negative", "good", "bad"):
            assert banned not in payload

    def test_reported_list_is_newest_first(self, client, db):
        now = datetime.now(timezone.utc)
        db[ECONOMIC_CALENDAR_EVENTS].insert_many([
            calendar_event(now - timedelta(days=3), "Oldest", actual=0.1),
            calendar_event(now - timedelta(days=1), "Newest", actual=0.2),
        ])

        reported = client.get("/market/economic-calendar").json()["reported"]
        assert [e["event"] for e in reported] == ["Newest", "Oldest"]

    def test_upcoming_list_is_chronological(self, client, db):
        now = datetime.now(timezone.utc)
        db[ECONOMIC_CALENDAR_EVENTS].insert_many([
            calendar_event(now + timedelta(days=5), "Later"),
            calendar_event(now + timedelta(days=1), "Sooner"),
        ])

        upcoming = client.get("/market/economic-calendar").json()["upcoming"]
        assert [e["event"] for e in upcoming] == ["Sooner", "Later"]


def indicator_reading(indicator: str, date: str, value: float) -> dict:
    return {"indicator": indicator, "date": date, "value": value,
            "source": "fmp", "collected_at": datetime.now(timezone.utc)}


def days_ago(n: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=n)).strftime("%Y-%m-%d")


class TestEconomicIndicators:
    def test_empty_collection_returns_200_with_no_tiles(self, client, db):
        r = client.get("/market/economic-indicators")
        assert r.status_code == 200
        assert r.json()["indicators"] == []

    def test_direction_and_change_null_when_no_prior_reading_exists(self, client, db):
        db[ECONOMIC_INDICATORS].insert_one(indicator_reading("GDP", days_ago(30), 31422.5))

        tiles = client.get("/market/economic-indicators").json()["indicators"]
        gdp = next(t for t in tiles if t["key"] == "growth")
        assert gdp["direction"] is None
        assert gdp["change"] is None
        assert gdp["value"] == 31422.5

    def test_direction_reflects_the_two_most_recent_readings(self, client, db):
        db[ECONOMIC_INDICATORS].insert_many([
            indicator_reading("inflationRate", days_ago(60), 2.50),
            indicator_reading("inflationRate", days_ago(30), 2.27),
        ])

        tiles = client.get("/market/economic-indicators").json()["indicators"]
        inflation = next(t for t in tiles if t["key"] == "inflation")
        assert inflation["direction"] == "down"
        assert inflation["change"] == pytest.approx(-0.23)
        assert inflation["as_of"] == days_ago(30)

    def test_flat_direction_when_the_two_latest_readings_are_equal(self, client, db):
        db[ECONOMIC_INDICATORS].insert_many([
            indicator_reading("federalFunds", days_ago(60), 3.88),
            indicator_reading("federalFunds", days_ago(30), 3.88),
        ])

        tiles = client.get("/market/economic-indicators").json()["indicators"]
        rate = next(t for t in tiles if t["key"] == "policy_rate")
        assert rate["direction"] == "flat"

    def test_lagging_true_past_90_days_false_within(self, client, db):
        db[ECONOMIC_INDICATORS].insert_many([
            indicator_reading("GDP", days_ago(120), 31000.0),
            indicator_reading("unemploymentRate", days_ago(10), 4.5),
        ])

        tiles = {t["key"]: t for t in client.get("/market/economic-indicators").json()["indicators"]}
        assert tiles["growth"]["lagging"] is True
        assert tiles["employment"]["lagging"] is False

    def test_tiles_appear_in_the_fixed_order(self, client, db):
        # Inserted out of order on purpose — response order must not follow insertion order
        db[ECONOMIC_INDICATORS].insert_many([
            indicator_reading("federalFunds", days_ago(10), 3.88),
            indicator_reading("GDP", days_ago(10), 31422.5),
            indicator_reading("unemploymentRate", days_ago(10), 4.5),
            indicator_reading("inflationRate", days_ago(10), 2.27),
        ])

        keys = [t["key"] for t in client.get("/market/economic-indicators").json()["indicators"]]
        assert keys == ["growth", "inflation", "employment", "policy_rate"]

    def test_a_series_never_fetched_is_omitted_not_null_valued(self, client, db):
        db[ECONOMIC_INDICATORS].insert_one(indicator_reading("GDP", days_ago(10), 31422.5))

        keys = [t["key"] for t in client.get("/market/economic-indicators").json()["indicators"]]
        assert keys == ["growth"]  # inflation/employment/policy_rate never fetched — absent, not null


class TestRiskPremium:
    def test_empty_collection_returns_200_with_null_values(self, client, db):
        r = client.get("/market/risk-premium")
        assert r.status_code == 200
        body = r.json()
        assert body["country"] is None
        assert body["total_equity_risk_premium"] is None
        assert body["country_risk_premium"] is None

    def test_returns_the_single_stored_us_row(self, client, db):
        db[MARKET_RISK_PREMIUM].insert_one({
            "country": "United States", "total_equity_risk_premium": 4.46,
            "country_risk_premium": 0.23, "source": "fmp",
            "collected_at": datetime(2026, 8, 20, tzinfo=timezone.utc),
        })

        body = client.get("/market/risk-premium").json()
        assert body["country"] == "United States"
        assert body["total_equity_risk_premium"] == 4.46
        assert body["country_risk_premium"] == 0.23
        assert body["collected_at"] == "2026-08-20T00:00:00+00:00"

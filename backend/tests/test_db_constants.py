"""Dead-collection-constant cleanup. Spec: specs/031-semantic-layer-chat;
research.md R7 (corrected findings — most of the originally-named "unused"
collections turned out not to exist at all; these four constants pointed at
collections that were never created).
"""
import db


def test_dead_collection_constants_are_removed():
    for name in ("FUND_HOLDINGS", "SECTOR_PERFORMANCE", "STOCK_NEWS", "MARKET_NEWS"):
        assert not hasattr(db, name), f"{name} should have been removed (research.md R7)"


def test_retained_collections_still_present():
    """transcripts_cache (reserved for specs/007-earnings-transcripts) and
    fmp_entitlements (actively written) must NOT be removed by the same
    cleanup pass — they only look unused because nothing has written to them
    yet in this environment."""
    assert db.TRANSCRIPTS_CACHE == "transcripts_cache"
    assert db.FMP_ENTITLEMENTS == "fmp_entitlements"


def test_strategy_signals_constant_pinned():
    """032-weekly-strategy-picks. Mirrored verbatim in
    agent-runner/tests/test_strategy_signals.py — the two services share no
    Python package, so this pinned-value pair IS the cross-service
    consistency check (constitution Principle VI): if either side's literal
    changes without the other, the collection name silently diverges and
    each service ends up reading/writing a different Mongo collection."""
    assert db.STRATEGY_SIGNALS == "strategy_signals"


def test_stock_events_constant_pinned():
    """037-stocks-conviction-and-activity. Mirrored verbatim in
    agent-runner/tests/test_db.py — same cross-service consistency check as
    STRATEGY_SIGNALS above."""
    assert db.STOCK_EVENTS == "stock_events"

"""market_news_pull — general/stock/FMP-article news ingestion.
Spec: specs/035-chat-and-news-upgrade; research.md R2/R7/R9; contracts/news-api.md.

Three feeds, one stored shape (`news_articles`). Upserts on `url` (research.md
R9 — the only realistic dedup key across three overlapping feeds), and
backfills the last BACKFILL_DAYS at launch, paced across runs to respect the
FMP daily budget: a `FmpBudgetExceededError` mid-pull is caught and the run
returns normally with whatever was ingested (constitution IV) rather than
propagating and being recorded as a failed job. Per-feed paging progress is
checkpointed in `dataset_meta` (keyed `news_<source_type>`, distinct from the
`news_articles` freshness marker `queue_worker._run_admin_job` writes
generically) so an interrupted backfill resumes from its next page rather
than re-paging from the start.
"""
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

import requests
from pymongo import DESCENDING
from pymongo.database import Database

import llm
from logging_config import get_logger
from settings import settings
from tools import news_enrich
from tools.db import DATASET_META, NEWS_ARTICLES
from tools.fmp_client import FmpBudgetExceededError, fmp_get

logger = get_logger(__name__)

# 036-news-semantic-search — dataset_meta checkpoint for the paced enrichment
# pass (research.md R7); distinct from the per-feed `news_<source_type>` paging
# checkpoints above and the generic `news_articles` freshness marker.
ENRICH_CHECKPOINT = "news_enrich"

BACKFILL_DAYS = 30
PAGE_SIZE = 100
# Per-run cap on backfill paging — the runaway guard, not the expected cost;
# keeps one job invocation from monopolizing the whole day's FMP budget on a
# single feed (mirrors tools/news.py's MAX_PAGES for the same reason).
MAX_PAGES_PER_RUN = 20

FEEDS: tuple[dict, ...] = (
    {"source_type": "general", "path": "news/general-latest"},
    {"source_type": "stock", "path": "news/stock-latest"},
    {"source_type": "fmp_article", "path": "fmp-articles"},
)

_TICKER_PREFIX_RE = re.compile(r"^[A-Za-z]+:")


class _TextExtractor(HTMLParser):
    """Minimal HTML->text: collects character data, drops tags/attributes.
    Good enough for the text index and the LLM's reading context (research.md
    R8) — the browser-facing render is a separate, sanitized HTML path."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self._parts).split())


def _strip_html(html: str | None) -> str:
    if not html:
        return ""
    parser = _TextExtractor()
    parser.feed(html)
    return parser.text()


def _parse_ticker_prefix(raw: str) -> str:
    """"NYSE:EXR" -> "EXR" — FMP articles carry an exchange-prefixed ticker
    string; the general/stock feeds don't (contracts/news-api.md)."""
    return _TICKER_PREFIX_RE.sub("", raw).strip().upper()


def _parse_published_at(raw: object) -> datetime | None:
    """Provider timestamps are naive UTC strings like "2026-08-25 06:20:17"
    or "2026-08-25T06:20:17"; anything else (missing, unparseable) is treated
    as an invalid article per data-model.md's validation rules."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()[:19].replace("T", " ")
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _normalize(row: dict, source_type: str) -> dict | None:
    """Maps one raw FMP row (from any of the three feeds) to the stored
    `news_articles` shape per contracts/news-api.md's mapping table. Returns
    None for a row missing a title/url, or with an unparseable published
    date — dropped rather than stored (data-model.md validation rules)."""
    if not isinstance(row, dict):
        return None

    if source_type == "fmp_article":
        url = (row.get("link") or "").strip()
        published_raw = row.get("date")
        author = row.get("author")
        publisher = author or row.get("site") or "unknown"
        body_html = row.get("content") or None
        body_text = _strip_html(body_html)
        raw_tickers = row.get("tickers")
        tickers = (
            [_parse_ticker_prefix(t) for t in raw_tickers.split(",") if t.strip()]
            if isinstance(raw_tickers, str) and raw_tickers
            else []
        )
    else:
        url = (row.get("url") or "").strip()
        published_raw = row.get("publishedDate")
        author = None
        publisher = row.get("publisher") or row.get("site") or "unknown"
        body_html = None
        body_text = row.get("text") or ""
        symbol = row.get("symbol")
        tickers = [symbol.strip().upper()] if source_type == "stock" and symbol else []

    title = (row.get("title") or "").strip()
    if not title or not url:
        return None

    published_at = _parse_published_at(published_raw)
    if published_at is None:
        return None

    return {
        "url": url,
        "source_type": source_type,
        "title": title,
        "published_at": published_at,
        "published_date": published_at.date().isoformat(),
        "publisher": publisher,
        "site": row.get("site"),
        "author": author,
        "body_html": body_html,
        "body_text": body_text,
        "image_url": row.get("image"),
        "tickers": tickers,
    }


def _checkpoint_key(source_type: str) -> str:
    return f"news_{source_type}"


def _load_checkpoint(db: Database, source_type: str) -> dict:
    doc = db[DATASET_META].find_one({"dataset": _checkpoint_key(source_type)}) or {}
    oldest = doc.get("oldest_published_at")
    # Mongo round-trips a naive datetime (UTC in practice) — reattach tzinfo
    # before it's compared against the tz-aware datetimes _normalize() produces.
    if oldest is not None and oldest.tzinfo is None:
        doc["oldest_published_at"] = oldest.replace(tzinfo=timezone.utc)
    return doc


def _save_checkpoint(
    db: Database, source_type: str, *, backfill_complete: bool,
    next_page: int, oldest_published_at: datetime | None,
) -> None:
    db[DATASET_META].update_one(
        {"dataset": _checkpoint_key(source_type)},
        {"$set": {
            "backfill_complete": backfill_complete,
            "next_page": next_page,
            "oldest_published_at": oldest_published_at,
            "checked_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )


def _upsert(db: Database, article: dict) -> None:
    db[NEWS_ARTICLES].update_one(
        {"url": article["url"]},
        {"$set": {**article, "ingested_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


def _pull_feed(db: Database, source_type: str, path: str) -> int:
    """Pages backward through one feed until the BACKFILL_DAYS floor is
    reached, the feed runs short, or the FMP budget is exhausted — the same
    stop-on-short-page/reached-cutoff/budget-exceeded shape already proven in
    tools/news.py::_fetch_window (research.md R7), adapted for feed-level
    rather than ticker-level paging. Once backfill is complete, later runs
    only fetch page 0 (the incremental steady state); overlap with what's
    already stored is absorbed for free by the unique-url upsert (research.md
    R9), so an exact resume offset is unnecessary once backfilled.
    """
    checkpoint = _load_checkpoint(db, source_type)
    backfill_complete = bool(checkpoint.get("backfill_complete"))
    was_already_complete = backfill_complete
    page = 0 if backfill_complete else checkpoint.get("next_page", 0)
    pages_this_run = 1 if backfill_complete else MAX_PAGES_PER_RUN
    cutoff = datetime.now(timezone.utc) - timedelta(days=BACKFILL_DAYS)
    oldest_seen = checkpoint.get("oldest_published_at")

    count = 0
    for _ in range(pages_this_run):
        try:
            rows = fmp_get(f"{path}?page={page}&limit={PAGE_SIZE}", db=db)
        except FmpBudgetExceededError:
            logger.warning(
                "%s: FMP budget spent mid-pull — keeping %s articles ingested this run, "
                "resuming at page %s next run", source_type, count, page,
            )
            _save_checkpoint(db, source_type, backfill_complete=False, next_page=page,
                              oldest_published_at=oldest_seen)
            return count
        except (requests.HTTPError, requests.RequestException) as exc:
            logger.warning(
                "%s: news fetch failed (%s) — keeping %s articles ingested this run, "
                "resuming at page %s next run", source_type, exc, count, page,
            )
            _save_checkpoint(db, source_type, backfill_complete=False, next_page=page,
                              oldest_published_at=oldest_seen)
            return count

        if not isinstance(rows, list) or not rows:
            backfill_complete = True
            break

        reached_cutoff = False
        for raw in rows:
            article = _normalize(raw, source_type)
            if article is None:
                continue
            if oldest_seen is None or article["published_at"] < oldest_seen:
                oldest_seen = article["published_at"]
            if article["published_at"] < cutoff:
                reached_cutoff = True
                continue
            _upsert(db, article)
            count += 1

        page += 1
        if len(rows) < PAGE_SIZE or reached_cutoff:
            backfill_complete = True
            break
    else:
        # Exhausted this run's page budget without a stopping signal (short
        # page / cutoff reached). In backfill mode that genuinely means not
        # done yet — resume from `page` next run. In steady-state mode
        # (a single page checked, was_already_complete=True) it only means
        # >=PAGE_SIZE new items arrived since the last check; the backfill
        # itself is still complete and must not be revoked, or every future
        # run would re-enter 20-page backfill mode against an always-full
        # "latest" feed and never converge (found live: general/fmp_article
        # feeds return a full page 0 on essentially every check).
        if not was_already_complete:
            backfill_complete = False

    _save_checkpoint(db, source_type, backfill_complete=backfill_complete, next_page=page,
                      oldest_published_at=oldest_seen)
    return count


def _enrichment_pending_filter() -> dict:
    """An article needs (re-)enrichment when it has no vector, its vector is
    from a superseded model (FR-013 self-heal, research.md R8), or its tag
    call previously failed and left `tags == []` (data-model.md §1 partial)."""
    return {"$or": [
        {"embedding": {"$exists": False}},
        {"embedding_model": {"$ne": settings.ollama_embed_model}},
        {"tags": []},
    ]}


def enrich_pending(db: Database, *, client=None, limit: int | None = None) -> int:
    """Paced enrichment pass (research.md R7): embeds + tags up to
    `news_enrich_batch_per_run` un-enriched / stale articles, newest first, so
    a handful of genuinely new stories from this same run are covered before
    the archive backfill drains. Writes the six enrichment fields and feeds
    each article's tags into the `news_tags` registry.

    Fail-soft: an `llm.LLMError` (Ollama down / model missing) stops the pass
    for this run with whatever was done so far — never propagates, so the
    news pull itself is still a successful job. Progress + the remaining count
    land in `dataset_meta['news_enrich']`."""
    batch = settings.news_enrich_batch_per_run if limit is None else limit
    pending = list(
        db[NEWS_ARTICLES].find(_enrichment_pending_filter())
        .sort("published_at", DESCENDING)
        .limit(batch)
    )

    enriched = 0
    tags_upserted = 0
    for doc in pending:
        try:
            fields = news_enrich._enrich(doc, client=client)
        except llm.LLMError as exc:
            logger.warning(
                "enrichment stopped after %s this run — embedding call failed: %s",
                enriched, exc,
            )
            break
        db[NEWS_ARTICLES].update_one({"_id": doc["_id"]}, {"$set": fields})
        if fields["tags"]:
            try:
                tags_upserted += news_enrich.upsert_tag_registry(
                    db, fields["tags"], client=client, now=datetime.now(timezone.utc),
                )
            except llm.LLMError as exc:
                logger.warning("tag-registry upsert failed for %s: %s", doc.get("url"), exc)
        enriched += 1

    remaining = db[NEWS_ARTICLES].count_documents(_enrichment_pending_filter())
    db[DATASET_META].update_one(
        {"dataset": ENRICH_CHECKPOINT},
        {"$set": {
            "enriched_last_run": enriched,
            "tags_upserted_last_run": tags_upserted,
            "remaining": remaining,
            "checked_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    if enriched or remaining:
        logger.info("enriched %s articles (%s tags upserted), %s remaining",
                    enriched, tags_upserted, remaining)
    return enriched


def run_market_news_pull(db: Database, *, client=None, enrich: bool = True) -> int:
    """Ingests all three FMP news feeds — general market, stock-specific, and
    FMP editorial articles — deduping on `url` and backfilling the last
    BACKFILL_DAYS at launch, paced across runs to respect the FMP daily
    budget (constitution IV; research.md R7). Never raises on a budget or
    provider failure for an individual feed — a partial run is a real,
    resumable success, not a job failure; the other feeds still land.

    After the pull, runs one paced enrichment batch (036 — embeddings + topic
    tags); `enrich=False` skips it (used where only pull mechanics are under
    test). The return value is the count of pulled/upserted articles,
    unchanged from before 036."""
    total = 0
    for feed in FEEDS:
        total += _pull_feed(db, feed["source_type"], feed["path"])
    if enrich:
        enrich_pending(db, client=client)
    return total

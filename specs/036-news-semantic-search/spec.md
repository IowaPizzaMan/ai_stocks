# Feature Specification: News Semantic Search with Tag Prefiltering

**Feature Branch**: `036-news-semantic-search`

**Created**: 2026-08-30

**Status**: Draft

**Input**: User description: "I want to do the bruite-foce cosine method. I also want to add tags for each news article so that helps prefilter the results before it does the bruite-force cosine filtration."

## Clarifications

### Session 2026-08-30

- Q: When someone asks why a named stock moved, or asks for a ticker's news on a particular topic, how should the chat pick which of that ticker's articles to answer from? → A: Hard-filter to that ticker's articles first, then semantic-rank those (blended with recency) and ground the answer in the top matches.
- Q: Is drilling into one specific already-mentioned story in scope (e.g. "tell me more about that Reuters piece")? → A: Out of scope for this feature — served only by the existing conversation-history replay.
- Q: Should semantic ranking factor in recency, or rank purely by similarity? → A: Blend similarity with a tunable age-decay, so fresher stories can outrank slightly-more-similar older ones.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Topic questions return news that is actually about the topic (Priority: P1)

A user asks the chat a question about a news topic that is not a specific ticker — for
example "what's the latest on chip export restrictions" or "any news about consumer
spending slowing down". Today the chat turns this into a keyword search, so it only
finds stories that literally contain those words. The user wants the chat to find
stories that are *about* that idea even when the wording is different ("semiconductor
sanctions", "retail demand softening"), and to ground its answer in those stories.

**Why this priority**: This is the core value of the feature and the reason the user
raised it. Keyword-only topic search is the current weakest part of the chat's news
answers — it silently misses relevant coverage, and the user cannot tell that it did.
Everything else in this spec exists to make this work well or make it fast.

**Independent Test**: Assemble a golden set of topic questions, each paired with the
stories a human considers relevant. Ask each question (including deliberately
reworded variants that share no keywords with the relevant stories) and confirm the
stories the chat cites are on-topic and include the reworded-case matches that the
current keyword path misses.

**Acceptance Scenarios**:

1. **Given** stored news that discusses "semiconductor export controls" without using
   the word "tariff", **When** the user asks "any recent news about trade restrictions
   on chips", **Then** the answer is grounded in those stories and cites them by
   headline and date.
2. **Given** two stories, one genuinely about the asked topic and one that merely
   mentions a keyword in passing, **When** the user asks the topic question, **Then**
   the genuinely on-topic story is ranked above the incidental-mention story.
3. **Given** no stored news is relevant to the topic, **When** the user asks, **Then**
   the chat says plainly that it found no relevant news rather than citing a weak match.

---

### User Story 2 - Tag prefiltering keeps topic search fast and focused (Priority: P2)

Every news article carries one or more topic tags assigned when it is ingested. When a
user's question clearly belongs to a tag area (e.g. "monetary policy", "earnings",
"M&A", "energy"), the chat narrows the pool of articles it compares against to just
those tagged articles before ranking them by relevance. This keeps the comparison cheap
as the news archive grows and removes whole categories of off-topic stories from
contention before ranking even starts.

**Why this priority**: The ranking method the user chose compares the question against
candidate articles one by one. Without a prefilter that cost grows with the size of the
archive, and unrelated stories can still produce spurious matches. Tag prefiltering is
what keeps P1 both fast and precise over time. It is P2 because P1 delivers value on its
own first (scored against the whole pool), and prefiltering is the optimization layered
on top.

**Independent Test**: With a tagged corpus, ask questions that map cleanly to a single
tag and confirm (a) only articles carrying that tag were scored, (b) the answer quality
matches or beats scoring the whole pool, and (c) end-to-end response time stays within
the chat latency target as the corpus is scaled up.

**Acceptance Scenarios**:

1. **Given** an archive where only 8% of stories are tagged "monetary policy", **When**
   the user asks "what did the Fed signal about rate cuts", **Then** only the
   "monetary policy" stories are ranked and the answer is drawn from them.
2. **Given** a question that maps to two tags, **When** the user asks it, **Then**
   articles carrying either tag are included in the ranked pool.
3. **Given** a question that maps to no known tag, **When** the user asks it, **Then**
   the chat still answers by ranking against the unfiltered recent-news pool rather
   than refusing.

---

### User Story 3 - "Why did this stock move" questions (Priority: P1)

A user asks "why did NVDA drop today", "what's behind the move in TSLA this week", or
asks for a ticker's news on a specific angle ("NVDA news about export restrictions").
The user wants an explanation grounded in the articles that actually discuss the move or
the angle — not just the most recent headlines for that ticker.

**Why this priority**: This is co-equal with User Story 1 — it was the first question
the user raised about how the feature would behave. Today a ticker-scoped news question
returns recent articles by date only, so "why did it move" often returns headlines that
explain nothing. Hard-filtering to the ticker's articles and then ranking them by
relevance-blended-with-recency is what makes this answerable.

**Independent Test**: With a corpus containing, for a given ticker, both articles that
explain a price move and unrelated same-ticker articles from the same days, ask "why did
<ticker> move" and confirm the explanatory articles are the ones cited.

**Acceptance Scenarios**:

1. **Given** NVDA articles from today where two explain a selloff and five are routine
   coverage, **When** the user asks "why did NVDA drop today", **Then** the answer is
   grounded in the two explanatory articles.
2. **Given** the user asks "NVDA news about export restrictions" and NVDA has articles
   on several topics, **When** the question is answered, **Then** only the
   export-restriction articles are cited, ranked by relevance and recency.
3. **Given** a plain "latest NVDA news" request, **When** the user asks, **Then**
   behavior is unchanged — most recent NVDA articles by date (User Story 4).

---

### User Story 4 - Existing ticker news and other chat answers are unchanged (Priority: P3)

A user asking "latest news on NVDA", or asking a screener question ("stocks near their
20-day lows"), sees exactly the same behavior as before this feature. Plain
ticker-scoped news still uses exact ticker matching with recency ordering; screener
questions are untouched.

**Why this priority**: This feature changes two paths — topic questions and
"why did it move" ticker-reason questions — and must not regress the rest (plain ticker
recency, screener). It is P3 because it is a guardrail, not new value: success here
means "nothing changed" for those flows.

**Independent Test**: Run the existing news and screener chat golden-question suites
unchanged and confirm no regression in the answers or the cited data.

**Acceptance Scenarios**:

1. **Given** stored news tagged to NVDA, **When** the user asks "latest NVDA news",
   **Then** the chat returns NVDA-tagged stories by recency, exactly as today.
2. **Given** a screener question, **When** the user asks it, **Then** the answer is
   identical to the pre-feature behavior.

---

### Edge Cases

- **Article with no usable text** (empty or near-empty body): it gets no semantic
  representation, is excluded from topic ranking, but remains reachable by ticker match
  and in the recency stream.
- **Question maps to no known tag**: fall back to ranking against the unfiltered recent
  pool (see FR-006) rather than refusing to answer.
- **Question maps to several tags**: the ranked pool is the union of those tag sets.
- **Free-form tag drift**: the same real-world topic accumulates several near-synonym
  tags over time ("fed", "federal reserve", "monetary policy"). Canonical-form
  normalization (FR-002a) collapses trivial variants; the near-miss question→tag match
  (FR-005) absorbs the rest. A question that matches only some of a topic's synonym
  tags still returns a useful, if slightly narrower, pool — acceptable, not a failure.
- **Tag on very few articles**: a highly specific tag carried by only one or two
  articles still prefilters correctly; if that pool is too small to answer well, the
  fallback to the unfiltered recent pool (FR-006) applies.
- **Embedding capability unavailable at question time**: the chat degrades to the
  current keyword/recency behavior for that question, with a short note, and never
  returns an error.
- **News archive is empty or tiny**: same "no relevant news found" behavior as today.
- **The embedding method changes** (different model/dimensions later): stored
  representations that no longer match the current method are detected and ignored for
  ranking rather than producing meaningless similarity scores; affected articles are
  re-processed.
- **Very long article body**: a deterministic, documented rule decides what portion of
  the text is represented, so the same article always yields the same representation.
- **Near-duplicate stories across the three feeds**: topic ranking can surface several
  near-identical stories; the number of stories used to ground a single answer is
  capped (see FR-008).
- **Tag prefilter empties the pool** (tag exists but no articles currently carry it):
  fall back to the unfiltered recent pool rather than returning nothing.
- **Move driven by market-wide news with no ticker tag**: ticker-reason mode
  hard-filters to the ticker's own articles, so a price move caused purely by a macro
  event that no ticker-tagged article covers may not be fully explained. Accepted
  limitation — ranking the whole archive with the ticker as a soft signal was
  considered and rejected for precision.
- **Ticker-reason question for a ticker with few or no articles**: falls back to plain
  recency for that ticker (User Story 4 behavior); if the ticker has no articles at
  all, the same "no relevant news found" response as today.
- **Follow-up about one specific already-mentioned story** ("tell me more about that
  Reuters piece", "what did the second article say about margins"): out of scope
  (FR-017) — answered only from whatever the existing conversation-history replay
  (spec 031) already carries, with no fresh single-article lookup.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST produce and store a semantic representation (a numeric
  vector) for each news article, derived from its headline and body text, at the time
  the article is ingested.
- **FR-002**: The system MUST assign one or more topic tags to each news article at
  ingestion time. Tags are an open, model-generated set — there is no fixed taxonomy;
  the ingestion step derives short topic labels from the article's own content.
- **FR-002a**: Because tags are free-form, the system MUST normalize them to a
  canonical form (e.g. lower-cased, trimmed, punctuation-stripped) before storage so
  that trivially different spellings of the same label collapse to one tag.
- **FR-002b**: The system MUST maintain a queryable list of the distinct tags currently
  in use across the archive, so the question→tag mapping step (FR-005) has a concrete
  vocabulary to match against.
- **FR-003**: The system MUST backfill semantic representations and topic tags for news
  articles already stored when this feature ships, as a one-time pass, so the existing
  archive is searchable the same way as newly ingested articles.
- **FR-004**: When a chat question seeks news by meaning rather than asking for a plain
  recency list, the system MUST rank candidate articles by a score that blends semantic
  closeness to the question with article recency (a documented age-decay), and ground
  the answer in the top-ranked articles. This covers two cases:
  - **Topic questions** (no specific ticker): the candidate pool is the tag-prefiltered
    pool (FR-005) or the unfiltered recent pool (FR-006).
  - **Ticker-reason questions** (a specific ticker plus a "why did it move" or a topic
    focus, e.g. "why did NVDA drop today", "NVDA news on export bans"): the candidate
    pool is first hard-filtered to that ticker's articles, then ranked the same way.
- **FR-004a**: The age-decay weighting in FR-004 MUST be a documented, tunable
  parameter, adjustable without changing the ranking logic.
- **FR-005**: The system MUST derive candidate topic labels from the question and match
  them against the in-use tag list (FR-002b). Because both sides are free-form, the
  match MUST tolerate near-misses (a question label of "interest rates" matching a
  stored tag of "monetary policy" / "fed rate decision"), not require string equality.
  When one or more tags match, semantic ranking is restricted to articles carrying
  those tags.
- **FR-006**: When a question maps to no known tag (or the matched tags currently have
  no articles), the system MUST rank against the unfiltered pool of recent articles
  rather than declining to answer.
- **FR-006a**: The system MUST apply a documented, tunable minimum semantic-closeness
  floor: an article whose closeness to the question is below the floor MUST NOT be used
  to ground the answer, even when it is the most recent in the fallback pool. When no
  candidate clears the floor the chat responds "no relevant news found" (US1 AS3).
  *(Added during implementation per constitution II — the recency-window fallback
  otherwise always returns weak citations for an off-topic question.)*
- **FR-007**: Semantic ranking MUST be computed by direct pairwise comparison between
  the question and each candidate article, requiring no database-native vector index and
  no new runtime service or hosted dependency — it MUST run on the current self-hosted
  data store as-is.
- **FR-008**: The system MUST cap the number of articles used to ground a single answer
  (default 10), and this cap MUST be adjustable without a code change to the ranking
  logic.
- **FR-009**: Answers grounded in news MUST continue to cite the specific stored
  articles they used by headline, date, and link, and MUST NOT introduce a headline or
  detail not present in those articles (unchanged from current behavior).
- **FR-010**: Plain ticker-scoped news questions — a ticker plus a request for
  latest/recent news, with no "why"/topic focus — MUST continue to be answered by exact
  ticker matching with recency ordering and no semantic ranking, exactly as today.
- **FR-010a**: The system MUST route each news question to one of three modes: plain
  ticker recency (FR-010), ticker-reason semantic rank (FR-004), or topic semantic rank
  (FR-004). A question that names a ticker AND expresses a "why"/topic focus MUST be
  routed to ticker-reason mode, not plain recency. The routing decision is made by the
  existing local model in the query-generation step.
- **FR-011**: If the semantic representation of the question cannot be produced at
  question time, the system MUST fall back to the current non-semantic news behavior and
  add a brief note to the answer; it MUST NOT return an error.
- **FR-012**: Articles that have no usable semantic representation MUST be excluded from
  semantic ranking while remaining available through ticker matching and the recency
  news stream.
- **FR-013**: The system MUST detect stored semantic representations that are
  incompatible with the current method (e.g. wrong dimensionality after a method change)
  and exclude them from ranking rather than scoring them, and MUST provide a way to
  re-process the affected articles.
- **FR-014**: For an archive of at least 25,000 articles (the expected size once news
  retention grows to roughly 90 days), an end-to-end topic or ticker-reason chat answer
  MUST complete within the existing chat latency target.
- **FR-015**: The description of the news collection shown to the chat model, and the
  mirrored field-vocabulary contract tests in both services, MUST be updated together to
  reflect the new stored fields (constitution Principle VI).
- **FR-016**: Topic tags are an internal retrieval aid only. They MUST NOT appear in the
  news stream UI, the news API response, or any user-facing surface in this feature.
- **FR-017**: Answering a follow-up about one specific already-mentioned story ("tell me
  more about that story", "what did the second article say") is OUT OF SCOPE for this
  feature. Such follow-ups are served only by whatever the existing conversation-history
  replay (spec 031) already carries; no new single-article lookup, resolution, or
  full-body drill-down behavior is built or tested here.

### Key Entities *(include if feature involves data)*

- **News Article** (existing): gains a semantic representation (numeric vector), a set
  of topic tags, an identifier for the method/version used to produce the representation,
  and a status indicating whether a usable representation exists.
- **Topic Tag**: a short, free-form topic label generated from an article's own
  content and stored in a normalized canonical form (FR-002a). There is no predefined
  list; the set of distinct tags is whatever the archive has accumulated (FR-002b).
  Relates many-to-many to News Article.
- **Question Representation**: the semantic representation of a user's question, computed
  per question and used only for ranking; not stored.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a golden set of topic questions, at least 80% of the articles the chat
  cites are judged on-topic by human review, up from the current keyword-path baseline
  (to be measured during planning).
- **SC-002**: On golden topic questions deliberately worded to share no keywords with
  the relevant articles, the chat cites at least one relevant article in at least 70% of
  cases, versus close to 0% for the current keyword path.
- **SC-003**: End-to-end response time for a topic or ticker-reason news question stays
  within the existing chat latency target with an archive of at least the size named in
  FR-014.
- **SC-004**: The existing news and screener chat golden-question suites pass with no
  regression.
- **SC-005**: Within one news-refresh cycle of ingestion, 100% of newly ingested
  articles that have usable text have both a semantic representation and at least one
  topic tag.
- **SC-006**: The feature adds no new runtime service, scheduler, or externally hosted
  dependency to the deployment.
- **SC-007**: When the embedding capability is unavailable, topic questions still return
  a non-error answer (degraded, with a note) in 100% of cases.
- **SC-008**: On a golden set of "why did <ticker> move" questions, at least 75% of the
  articles the chat cites are judged by human review to actually address the move, up
  from a recency-only baseline to be measured during planning.

## Assumptions

- Direct pairwise cosine comparison over an in-memory candidate set is fast enough at
  this project's news volume; a database-native vector index is explicitly not needed
  now and is a possible future change, not part of this feature.
- Semantic representations and tags are produced by the existing local model runtime as
  part of the existing news-ingestion job — no new scheduler, no new service. A
  dedicated embedding-capable model is available in that runtime alongside the chat
  model.
- The one-time backfill covers the existing ~30-day archive; steady-state maintenance
  happens per article at ingestion.
- The existing per-URL deduplication remains the article's identity; the new fields
  attach to that record.
- Mapping a question to candidate tags is done by the existing local model as part of,
  or immediately alongside, the current query-generation step, matched against the
  in-use tag list rather than a fixed vocabulary.
- Free-form tagging is accepted as less precise than a curated taxonomy; canonical
  normalization plus near-miss matching plus the unfiltered fallback are considered
  sufficient to keep the prefilter useful without a maintained tag list.
- A question that names a ticker and also expresses a "why" or topic focus is routed to
  ticker-reason semantic ranking (FR-004/FR-010a) — the ticker's articles are
  hard-filtered first, then ranked by similarity blended with recency. Plain "latest
  news on <ticker>" stays recency-only.
- Single-story drill-down follow-ups are out of scope (FR-017); the existing
  conversation-history replay from spec 031 is considered sufficient for them for now.
- Screener questions are entirely unaffected.
- Retention: the semantic representation and tags live and die with their article; there
  is no separate retention policy for them.
- This feature builds on specs/031-semantic-layer-chat (the chat flow and latency
  target) and specs/035-chat-and-news-upgrade (the `news_articles` collection and the
  cross-service schema-mirroring discipline).

## Dependencies

- An embedding-capable local model must be available in the existing model runtime.
- The existing news-ingestion job is the insertion point for producing representations
  and tags.
- The chat query-generation and answer-interpretation flow from spec 031 is the
  insertion point for question representation, tag mapping, and ranking.

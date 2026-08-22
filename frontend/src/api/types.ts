export type Signal = "bullish" | "bearish" | "neutral";
export type Conviction = "high" | "medium" | "low";

export interface PositionManagement {
  stair_step_stops: number[];
  trailing_stop_recommendation: string;
  position_sizing: string;
}

export interface AnalysisFeedItem {
  ticker: string;
  timestamp: string;
  signal: Signal;
  conviction: Conviction;
  summary: string;
  key_trends: string[];
  flags: string[];
  sector?: string | null;
  position_management?: PositionManagement;
  // Feed flags — absent on analyses written before these existed
  recent_institutional_activity?: "buying" | "selling" | "mixed" | null;
  recent_insider_summary?: string | null; // e.g. "10 buys, 2 sells"
}

export interface Analysis extends AnalysisFeedItem {
  sub_reports: SubReports;
  // 021 — absent on analyses written before this feature / on first-ever pulls
  changes_since_last?: ChangesSinceLast | null;
}

export interface SubReports {
  technical?: TechnicalReport;
  fundamental?: FundamentalReport;
  macro?: MacroReport;
  insider?: InsiderReport;
  institutional?: InstitutionalReport;
  sentiment?: SentimentReport;
  recommendation?: RecommendationReport;
  news?: NewsReport;
}

// --- 021-stock-page-redesign ------------------------------------------------
// Every field below is optional on read: analyses stored before 021 lack them
// entirely, so consumers must render an empty state rather than assume presence.
// Contract: specs/021-stock-page-redesign/contracts/analysis-subreports.md

export interface NewsArticle {
  date: string;
  datetime: string;
  source: string;
  headline: string;
  url: string;
  text_excerpt: string;
  bullish_count: number;
  bearish_count: number;
  ai_summary: string | null; // only the newest articles get one
}

export interface TimelinePoint {
  date: string;
  bullish: number;
  bearish: number;
  article_count: number;
}

export type NewsTrend = "bullish" | "bearish" | "mixed";

export interface NewsReport {
  articles: NewsArticle[]; // newest first, full 30-day window
  timeline: TimelinePoint[]; // ascending by date
  trend: NewsTrend;
  stance: { direction: "bullish" | "neutral" | "bearish"; reasoning: string } | null;
  news_count: number;
  days_covered?: number; // days in the window that actually had coverage
  window_days?: number; // the window that was requested (30)
  as_of?: string | null;
}

export interface InsiderQuarterStats {
  year: number;
  quarter: number;
  acquired_transactions: number;
  disposed_transactions: number;
  acquired_disposed_ratio: number;
  total_acquired: number;
  total_disposed: number;
  total_purchases: number;
  total_sales: number;
}

export interface BeneficialFiling {
  filer: string;
  filing_date: string;
  shares: number;
  pct_of_class: number;
  filer_type: string;
  url: string;
}

// --- 022-market-news-feed ---------------------------------------------------
// Market-wide headlines shown on the Stocks page. Deliberately NOT related to
// NewsArticle above: that one carries per-ticker sentiment counts and an AI
// summary, none of which apply to this plain headline list.
// Contract: specs/022-market-news-feed/contracts/market-news-endpoint.md

export interface MarketNewsArticle {
  ticker: string | null; // null for untagged market commentary
  datetime: string;
  date: string;
  source: string;
  headline: string;
  url: string;
  text_excerpt: string;
}

export interface MarketNewsResponse {
  articles: MarketNewsArticle[]; // <= 20, newest first
  as_of: string | null;
  stale: boolean; // true when the cached copy could not be refreshed
}

export interface ChangesSinceLast {
  previous_timestamp: string;
  signal: { from: string; to: string; changed: boolean };
  conviction: { from: string; to: string; changed: boolean };
  flags_added: string[];
  flags_removed: string[];
}

export interface OHLCVBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface PriceResponse {
  ticker: string;
  resolution: "daily" | "weekly" | "monthly";
  bars: OHLCVBar[];
}

export interface MacroReport {
  overall_macro_signal: Signal;
  confidence: Conviction;
  inflation_impact: { trend: string; impact_on_sector: string; cpi_latest?: number | null };
  rate_impact: { direction: string; impact_on_valuation: string; fed_funds_rate?: number | null };
  growth_backdrop: {
    recession_signal: string;
    commentary: string;
    yield_curve_spread?: number | null;
    curve_inverted?: boolean;
  };
  consumer_backdrop: string;
  sector_rotation_signal: string;
}

// One sector's macro read, produced independently of ticker analysis by the
// agent-runner's macro worker (specs/020-surface-macro-ui).
export interface SectorMacroRead extends MacroReport {
  sector: string;
  computed_at: string;
}

export interface MacroReads {
  sectors: SectorMacroRead[];
  as_of: string | null;
}

export interface InsiderTransaction {
  name: string;
  transaction_type: string;
  shares: number;
  price_per_share: number;
  total_value: number;
  date: string;
  filing_date: string;
  is_open_market: boolean;
}

export interface InsiderReport {
  overall_insider_signal: Signal;
  confidence: Conviction;
  narrative: string;
  recent_transactions: InsiderTransaction[];
  cluster_signal: { detected: boolean; insiders: string[]; window_days: number | null };
  net_direction: string;
  key_buyers: string[];
  mspr_trend: { direction: string; commentary: string };
  unusual_size: string;
  signal_strength: string;
  as_of?: string | null; // most recent Form 4 transaction date in the lookback window
  quarterly_stats?: InsiderQuarterStats[]; // 021 — newest first, ≤8 quarters
}

export interface InstitutionalReport {
  overall_institutional_signal: Signal;
  confidence: Conviction;
  narrative: string;
  institutional_summary: {
    ownership_pct: number | null;
    institutions_count: number | null;
    insiders_pct: number | null;
    top10_increasing: number | null;
    top10_decreasing: number | null;
    as_of: string | null;
  };
  notable_increases: string[];
  notable_reductions: string[];
  superinvestor_available: boolean;
  superinvestor_moves: { fund: string; action: string; ticker: string; detail?: string }[];
  superinvestor_read: string;
  concentration_assessment: string;
  as_of?: string | null; // same date as institutional_summary.as_of, at top level for consistency
  // 021 — 13D/G filings are the entitled institutional signal (13F is not)
  beneficial_filings?: BeneficialFiling[]; // newest first, ≤20
  beneficial_direction?: "accumulating" | "distributing" | "mixed" | null;
}

export interface SentimentReport {
  overall_sentiment_signal: string;
  confidence: Conviction;
  current_tone: string;
  tone_evidence: string[];
  earnings_surprise_read: string;
  narrative: string;
  news_count: number;
  transcripts_available: boolean;
  bullish_keywords: { terms: string[]; count: number };
  cautious_keywords: { terms: string[]; count: number };
  as_of?: string | null; // most recent headline date in the news window
}

export interface SectorSummary {
  sector: string;
  bullish_count: number;
  bearish_count: number;
  neutral_count: number;
  ticker_count: number;
  top_ticker: string | null;
}

export interface FeedResponse {
  items: AnalysisFeedItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface TechnicalReport {
  overall_technical_signal: Signal;
  confidence: Conviction;
  momentum_summary: string;
  tfc_narrative: string;
  bf_position_narrative: string;
  volume_narrative: string;
  key_levels?: { support: number[]; resistance: number[] };
  accumulation_result?: { accumulation_score: number; signal: string; rationale?: string };
  gap_result?: { signal?: string };
  strat_result?: { signal?: string; tfc?: { status: string } };
  as_of?: string | null; // latest daily price bar this read is based on
}

export interface FundamentalReport {
  overall_fundamental_signal: Signal;
  confidence: Conviction;
  narrative: string;
  revenue_trend?: { direction: string; history_annual: Record<string, unknown>[] };
  margin_trend?: { direction: string };
  balance_sheet_health?: { assessment: string };
  fcf_profile?: { assessment: string };
  valuation_assessment?: { view: string };
  as_of?: string | null; // most recent reported statement date
}

export interface RecommendationReport {
  recommendation: string;
  conviction: string;
  rationale: string;
  nymo_current: number | null;
  namo_current: number | null;
  nymo_signal: string;
  caveats: string[];
  breadth_signal?: string;
  nymo_reading?: { value: number | null; trend: string | null; zone: string | null };
  namo_reading?: { value: number | null; trend: string | null; zone: string | null };
  divergence_detected?: boolean;
  gap_score_summary?: {
    latest_gap: { direction: string; type: string; score: number } | null;
    exhaustion_present: boolean;
  };
}

// --- Market breadth (GET /market/breadth) ------------------------------------
// Served from breadth_cache; the oscillator math and divergence detection run
// in agent-runner/tools/breadth.py, not here.

export type DivergenceType = "bullish" | "bearish" | "none";

export interface BreadthPoint {
  date: string;
  value: number;
}

export interface SpyPoint {
  date: string;
  close: number;
}

export interface DivergenceAnchor {
  date: string;
  value: number;
}

export interface Divergence {
  type: DivergenceType;
  description: string;
  // The two swing highs/lows on each series — the chart draws its
  // opposite-sloping trend lines straight from these.
  price_points: DivergenceAnchor[];
  osc_points: DivergenceAnchor[];
}

export interface ResolvedDivergence {
  type: Exclude<DivergenceType, "none">;
  detected_on: string;
  resolved: string;
  anchor_dates: string[];
  description?: string | null;
  spy_change_5d: number | null; // SPY follow-through after the resolution date
  spy_change_10d: number | null;
}

export interface MarketBreadth {
  spy: SpyPoint[];
  nymo: BreadthPoint[];
  namo: BreadthPoint[];
  divergence: Divergence;
  divergence_history: ResolvedDivergence[];
  as_of: string | null;
  method: string;
}

export interface MarketFlowEvent {
  event_id: string;
  category: "market_flow";
  kind: "breadth_divergence";
  divergence_type: Exclude<DivergenceType, "none">;
  headline: string;
  body: string;
  price_points: DivergenceAnchor[];
  osc_points: DivergenceAnchor[];
  nymo_current: number | null;
  detected_on: string;
  created_at: string;
}

// --- Economics dashboard (specs/026-macro-market-dashboard) -----------------
// GET /market/treasury-curve, /market/economic-calendar,
// /market/economic-indicators, /market/risk-premium — all read-only shapes
// over what agent-runner/tools/economics.py already wrote; see
// specs/026-macro-market-dashboard/contracts/macro-api.md.

export interface Freshness {
  as_of: string | null;
  stale: boolean;
}

export interface CurvePoint {
  maturity: string; // "1M".."30Y"
  months: number; // proportional x-axis value, not an evenly-spaced category
  current: number | null;
  month_ago: number | null;
  year_ago: number | null;
}

export type SpreadKey = "10y-2y" | "30y-10y" | "10y-3m";

export interface SpreadSeriesPoint {
  date: string;
  bps: number;
}

export interface Spread {
  key: SpreadKey;
  label: string;
  current_bps: number | null;
  change_bps: number | null;
  inverted: boolean;
  series: SpreadSeriesPoint[];
}

export interface TreasuryCurve extends Freshness {
  session: string | null;
  curve: CurvePoint[];
  comparison_sessions: { month_ago: string | null; year_ago: string | null };
  spreads: Spread[];
}

export type CalendarComparison = "above" | "below" | "in_line" | null;

export interface EconomicEvent {
  date: string;
  event: string;
  impact: "High" | "Medium";
  previous: number | null;
  estimate: number | null;
  unit: string | null;
}

export interface ReportedEconomicEvent extends EconomicEvent {
  actual: number;
  comparison: CalendarComparison;
  surprise: number | null;
}

export interface EconomicCalendar extends Freshness {
  timezone: string;
  upcoming: EconomicEvent[];
  reported: ReportedEconomicEvent[];
}

export type IndicatorDirection = "up" | "down" | "flat" | null;

export interface IndicatorTile {
  key: string;
  label: string;
  series: string;
  value: number;
  unit: string;
  as_of: string;
  direction: IndicatorDirection;
  change: number | null;
  lagging: boolean;
}

export interface EconomicIndicators extends Freshness {
  indicators: IndicatorTile[];
}

export interface RiskPremium extends Freshness {
  country: string | null;
  total_equity_risk_premium: number | null;
  country_risk_premium: number | null;
  collected_at: string | null;
}

// 024-delta-data-pulls: delta is the default; "full" is the operator's
// rebuild-from-scratch escape hatch. Absent on jobs queued before the feature.
export type PullMode = "delta" | "full";

export interface QueueJob {
  ticker?: string; // absent on non-ticker admin jobs, e.g. job_type "portfolio_digest"
  job_type?: string; // absent = ordinary per-ticker analysis job
  status: string;
  source?: string;
  created_at: string;
  mode?: PullMode;
}

export interface QueueStatus {
  pending: QueueJob[];
  running: QueueJob[];
  pending_count: number;
  running_count: number;
}

export interface EnqueueResponse {
  ticker: string;
  job_id: string;
  status: "enqueued" | "already_queued" | "upgraded_to_full";
  mode?: PullMode;
}

// 024-delta-data-pulls (US1) — per-stage pull cost
export type StageRetrieval = "incremental" | "full" | "stored";
export type StageOutcome = "fetched" | "stored" | "degraded" | "skipped" | "failed";

export interface PullStage {
  name: string;
  elapsed_ms: number;
  requests: number;
  bytes: number;
  retrieval: StageRetrieval | null;
  outcome: StageOutcome | null;
}

export interface Pull {
  job_id: string;
  mode: PullMode;
  started_at: string;
  completed_at: string;
  total_ms: number;
  outcome: "done" | "failed" | "degraded";
  /** Server-sorted most-expensive-first, so the client never re-ranks. */
  stages: PullStage[];
  accounted_ms: number;
  /** Wall time the stage breakdown does not explain — surfaced, not hidden. */
  unaccounted_ms: number;
}

export interface PullMetrics {
  ticker: string;
  pulls: Pull[];
}

/** spec: specs/025-earnings-page-filters/contracts/earnings-calendar.md.
 * `report_time` (bmo/amc) is gone — the FMP source that carries actuals has
 * no time-of-day field (research.md D4). */
export type EarningsReportingState = "upcoming" | "reported" | "awaiting";

export interface EarningsCalendarEntry {
  ticker: string;
  company: string;
  sector: string | null;
  market_cap: number;
  report_date: string;
  eps_estimate: number | null;
  eps_actual: number | null;
  revenue_estimate: number | null;
  revenue_actual: number | null;
  eps_surprise_pct: number | null;
  revenue_surprise_pct: number | null;
  beat: boolean | null;
  reporting_state: EarningsReportingState;
  last_updated: string;
}

export interface EarningsCalendarResponse {
  entries: EarningsCalendarEntry[];
  total_before_screen: number;
  stale: boolean;
  fetched_at: string;
}

export type FlowAction = "new_position" | "add" | "trim" | "exit";

export interface InstitutionalFlowEvent {
  ticker: string;
  fund: string;
  action: FlowAction;
  shares: number | null;
  value_usd: number | null;
  pct_of_portfolio: number | null;
  pct_change: number | null; // QoQ position change (13F rows), 1.0 = +100%
  headline: string;
  notability_score: number;
  source: "13F" | "dataroma";
  filed_at: string;
  scanned_at: string;
}

export interface InstitutionalFlowResponse {
  items: InstitutionalFlowEvent[];
  total: number;
  page: number;
  page_size: number;
}

// Raw FMP payload shapes returned by GET /stocks/{ticker}/financials — the
// backend passes these through unchanged (agent-runner/tools/financials.py
// caches FMP's stable/ratios + stable/key-metrics responses verbatim), so
// these field names are FMP's real field names, not an app-defined schema.
// Only fields actually read by FundamentalsTab are typed explicitly; each
// interface keeps an index signature for the rest of FMP's payload.
// Arrays are newest-first (FMP convention) — reverse for chronological x-axes.
export interface FMPIncomeStatement {
  date: string;
  period: string;
  calendarYear?: string;
  revenue: number;
  grossProfit: number;
  operatingIncome: number;
  netIncome: number;
  eps: number;
  epsDiluted: number;
  sellingGeneralAndAdministrativeExpenses?: number;
  generalAndAdministrativeExpenses?: number;
  sellingAndMarketingExpenses?: number;
  [key: string]: unknown;
}

export interface FMPBalanceSheetStatement {
  date: string;
  totalCurrentAssets: number;
  totalCurrentLiabilities: number;
  totalDebt: number;
  cashAndCashEquivalents: number;
  netDebt: number;
  totalStockholdersEquity: number;
  accruedExpenses?: number;
  taxPayables?: number;
  [key: string]: unknown;
}

export interface FMPCashFlowStatement {
  date: string;
  netIncome?: number;
  operatingCashFlow: number;
  capitalExpenditure: number;
  freeCashFlow: number;
  commonStockRepurchased?: number;
  commonDividendsPaid?: number;
  [key: string]: unknown;
}

export interface FMPRatios {
  date: string;
  priceToEarningsRatio: number | null;
  priceToSalesRatio: number | null;
  priceToBookRatio: number | null;
  enterpriseValueMultiple: number | null; // canonical EV/EBITDA — key_metrics.evToEBITDA is a duplicate, don't chart both
  priceToFreeCashFlowRatio: number | null;
  priceToEarningsGrowthRatio: number | null; // PEG — unstable near-zero growth, clamp before charting
  dividendYield: number | null;
  grossProfitMargin: number | null;
  operatingProfitMargin: number | null;
  ebitdaMargin: number | null;
  netProfitMargin: number | null;
  debtToEquityRatio: number | null;
  currentRatio: number | null;
  quickRatio: number | null;
  operatingCashFlowRatio: number | null;
  interestCoverageRatio: number | null; // renders as 0 near-zero net interest expense — treat as "N/A" below a threshold
  [key: string]: unknown;
}

export interface FMPKeyMetrics {
  date: string;
  returnOnEquity: number | null; // can exceed 100% for heavy-buyback companies — needs a caption, not a bug
  returnOnInvestedCapital: number | null;
  returnOnAssets: number | null;
  returnOnCapitalEmployed?: number | null;
  freeCashFlowYield: number | null;
  capexToRevenue?: number | null;
  daysOfSalesOutstanding: number | null;
  daysOfInventoryOutstanding: number | null;
  daysOfPayablesOutstanding: number | null;
  cashConversionCycle: number | null;
  evToEBITDA?: number | null; // duplicate of ratios.enterpriseValueMultiple — don't chart this one
  [key: string]: unknown;
}

export interface FMPGrowth {
  date: string;
  growthRevenue: number | null;
  growthNetIncome: number | null;
  growthEPS: number | null;
  [key: string]: unknown;
}

export interface StockFinancials {
  income_annual: FMPIncomeStatement[];
  income_quarterly: FMPIncomeStatement[];
  balance_annual: FMPBalanceSheetStatement[];
  cashflow_annual: FMPCashFlowStatement[];
  ratios: FMPRatios[];
  key_metrics: FMPKeyMetrics[];
  growth: FMPGrowth[];
}

export interface WatchlistItem {
  ticker: string;
  name?: string | null;
  sector?: string | null;
  status: string;
  last_signal?: Signal;
  last_conviction?: Conviction;
  last_analyzed?: string;
}

// 027-stocks-news-tab-ai-summary — cross-stock AI summary panel on the Stocks
// page. Contract: specs/027-stocks-news-tab-ai-summary/contracts/portfolio-digest-api.md

export interface PortfolioDigestHighlight {
  ticker: string;
  signal: Signal;
  conviction: Conviction;
  note: string;
}

export interface PortfolioDigestResponse {
  as_of: string | null; // generated_at of the last successful synthesis
  overview: string | null;
  highlights: PortfolioDigestHighlight[];
  stock_count: number;
  total_tracked_count: number;
  capped: boolean;
  stale: boolean; // true when a regeneration attempt failed more recently than the last success
}

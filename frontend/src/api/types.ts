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
}

export interface SubReports {
  technical?: TechnicalReport;
  fundamental?: FundamentalReport;
  macro?: MacroReport;
  insider?: InsiderReport;
  institutional?: InstitutionalReport;
  sentiment?: SentimentReport;
  recommendation?: RecommendationReport;
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

export interface QueueJob {
  ticker: string;
  status: string;
  source?: string;
  created_at: string;
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
  status: "enqueued" | "already_queued";
}

export interface EarningsCalendarEntry {
  ticker: string;
  company: string;
  report_date: string;
  report_time: "bmo" | "amc" | "unknown";
  eps_estimate: number | null;
  revenue_estimate: number | null;
  market_cap: number;
  sector: string | null;
}

export interface EarningsScoreBreakdown {
  move_pts: number;
  beat_pts: number;
  revision_pts: number;
  insider_pts: number;
  accumulation_pts: number;
}

export interface EarningsCandidate {
  ticker: string;
  company: string;
  report_date: string;
  report_time: "bmo" | "amc" | "unknown";
  sector: string | null;
  market_cap: number;
  score: number;
  score_breakdown: EarningsScoreBreakdown;
  avg_abs_move_pct: number;
  beat_rate: number;
  history_quarters: number;
  eps_revision: "up" | "flat" | "down";
  insider_signal: "cluster" | "single" | "none";
  accumulation_score: number;
  one_line_thesis: string;
}

export interface EarningsScanDoc {
  scan_id: string;
  status: "pending" | "running" | "complete" | "failed";
  days_ahead: number;
  candidates?: EarningsCandidate[];
  total_screened?: number;
  scored_count?: number;
  top_count?: number;
  error?: string;
}

export interface EarningsQuarter {
  period: string;
  eps_estimate: number | null;
  eps_actual: number | null;
  surprise_pct: number | null;
  beat: boolean;
  move_pct: number;
  move_abs: number;
}

export interface EarningsHistory {
  ticker: string;
  quarters: EarningsQuarter[];
  avg_abs_move_pct: number;
  beat_rate: number;
  num_quarters: number;
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

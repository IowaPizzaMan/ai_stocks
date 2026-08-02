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

export interface WatchlistItem {
  ticker: string;
  name?: string | null;
  sector?: string | null;
  status: string;
  last_signal?: Signal;
  last_conviction?: Conviction;
  last_analyzed?: string;
}

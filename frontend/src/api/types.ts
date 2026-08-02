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
  sub_reports: {
    technical?: TechnicalReport;
    fundamental?: FundamentalReport;
    recommendation?: RecommendationReport;
  };
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

export interface WatchlistItem {
  ticker: string;
  name?: string | null;
  sector?: string | null;
  status: string;
  last_signal?: Signal;
  last_conviction?: Conviction;
  last_analyzed?: string;
}

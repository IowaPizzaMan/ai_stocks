// Spec: specs/component-specs/frontend/components/stock/PriceChart.md "Display Windowing"
// 021-stock-page-redesign adds the four Charts-tab panel timeframes (D/W/M/Y).
// These are resolution-true: a "M" candle is one calendar month, not a
// one-month window of daily bars — which is what the legacy "1M" entry means
// and why the monthly panel used to look wrong.
export type Timeframe = "1D" | "1W" | "1M" | "1Y" | "5Y" | "MAX" | "D" | "W" | "M" | "Y";

/** The four Charts-tab panels, in render order. */
export const PANEL_TIMEFRAMES: Timeframe[] = ["D", "W", "M", "Y"];

export const PANEL_LABELS: Partial<Record<Timeframe, string>> = {
  D: "Daily",
  W: "Weekly",
  M: "Monthly",
  Y: "Yearly",
};

const DISPLAY_COUNT: Record<Timeframe, { full: number; compact: number }> = {
  "1D": { full: 90, compact: 60 },
  "1W": { full: 78, compact: 52 },
  "1M": { full: 30, compact: 21 },
  "1Y": { full: 252, compact: 180 },
  "5Y": { full: 260, compact: 156 },
  MAX: { full: 240, compact: 120 },
  // Charts-tab panels — counts are in bars of that panel's own resolution
  D: { full: 90, compact: 90 },
  W: { full: 78, compact: 78 },
  M: { full: 36, compact: 36 }, // ~3 years of monthly candles
  Y: { full: 15, compact: 15 }, // 10–15 years of yearly candles
};

export function sliceForDisplay<T>(bars: T[], tf: Timeframe, compact: boolean): T[] {
  const count = compact ? DISPLAY_COUNT[tf].compact : DISPLAY_COUNT[tf].full;
  return bars.slice(-count);
}

/** Bar resolution each timeframe renders at (PriceChart.md table). */
export const TIMEFRAME_RESOLUTION: Record<Timeframe, "daily" | "weekly" | "monthly" | "yearly"> = {
  "1D": "daily",
  "1W": "weekly",
  "1M": "daily",
  "1Y": "daily",
  "5Y": "weekly",
  MAX: "monthly",
  D: "daily",
  W: "weekly",
  M: "monthly",
  Y: "yearly",
};

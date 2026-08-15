// Spec: specs/component-specs/frontend/components/stock/PriceChart.md "Display Windowing"
export type Timeframe = "1D" | "1W" | "1M" | "1Y" | "5Y" | "MAX";

const DISPLAY_COUNT: Record<Timeframe, { full: number; compact: number }> = {
  "1D": { full: 90, compact: 60 },
  "1W": { full: 78, compact: 52 },
  "1M": { full: 30, compact: 21 },
  "1Y": { full: 252, compact: 180 },
  "5Y": { full: 260, compact: 156 },
  MAX: { full: 240, compact: 120 },
};

export function sliceForDisplay<T>(bars: T[], tf: Timeframe, compact: boolean): T[] {
  const count = compact ? DISPLAY_COUNT[tf].compact : DISPLAY_COUNT[tf].full;
  return bars.slice(-count);
}

/** Bar resolution each timeframe renders at (PriceChart.md table). */
export const TIMEFRAME_RESOLUTION: Record<Timeframe, "daily" | "weekly" | "monthly"> = {
  "1D": "daily",
  "1W": "weekly",
  "1M": "daily",
  "1Y": "daily",
  "5Y": "weekly",
  MAX: "monthly",
};

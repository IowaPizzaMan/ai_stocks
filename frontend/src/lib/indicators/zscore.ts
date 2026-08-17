// Price z-score — how many standard deviations the close sits from its
// 20-period mean. Spec 021 FR-007. Reads as "stretched" vs "at fair value"
// within the timeframe's own recent history.
import type { OHLCVBar } from "../../api/types";

export const ZSCORE_WARMUP = 20;

export interface ZScorePoint {
  date: string;
  zscore: number | null;
}

export function computeZScore(bars: OHLCVBar[], period = 20): ZScorePoint[] {
  return bars.map((b, i) => {
    if (i + 1 < period) return { date: b.date, zscore: null };
    const window = bars.slice(i + 1 - period, i + 1).map((w) => w.close);
    const mean = window.reduce((a, v) => a + v, 0) / period;
    const variance = window.reduce((a, v) => a + (v - mean) ** 2, 0) / period;
    const sd = Math.sqrt(variance);
    // Zero variance (a perfectly flat window) means the close is exactly at
    // its mean — z of 0, not a divide-by-zero.
    return { date: b.date, zscore: sd === 0 ? 0 : (b.close - mean) / sd };
  });
}

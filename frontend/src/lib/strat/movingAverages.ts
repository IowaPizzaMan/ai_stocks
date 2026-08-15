// Spec: specs/component-specs/frontend/components/stock/PriceChart.md "Moving Averages"
import type { OHLCVBar } from "../../api/types";

export const MOVING_AVERAGES = [
  { key: "ema8", period: 8, type: "ema", color: "#f472b6", style: "solid" },
  { key: "ema21", period: 21, type: "ema", color: "#facc15", style: "solid" },
  { key: "ema50", period: 50, type: "ema", color: "#38bdf8", style: "solid" },
  { key: "ema200", period: 200, type: "ema", color: "#a78bfa", style: "solid" },
  { key: "sma10", period: 10, type: "sma", color: "#4ade80", style: "dashed" },
  { key: "sma30", period: 30, type: "sma", color: "#fb923c", style: "dashed" },
  { key: "sma90", period: 90, type: "sma", color: "#f87171", style: "dashed" },
] as const;

export type BarWithMAs = OHLCVBar & Record<string, number | string | null>;

function sma(values: number[], period: number, i: number): number | null {
  if (i + 1 < period) return null;
  let sum = 0;
  for (let j = i + 1 - period; j <= i; j++) sum += values[j];
  return sum / period;
}

function ema(
  values: number[],
  period: number,
  i: number,
  prev: number | null,
): number | null {
  if (i + 1 < period) return null;
  if (prev == null) return sma(values, period, i); // seed with SMA
  const k = 2 / (period + 1);
  return values[i] * k + prev * (1 - k);
}

/** Computes all 7 MAs against the FULL fetched history (display trimming
 * happens separately) so a 200-period MA is a real 200-bar average. */
export function computeMovingAverages(bars: OHLCVBar[]): BarWithMAs[] {
  const closes = bars.map((b) => b.close);
  const out: BarWithMAs[] = bars.map((b) => ({ ...b }));
  for (const ma of MOVING_AVERAGES) {
    let prev: number | null = null;
    for (let i = 0; i < bars.length; i++) {
      const v: number | null =
        ma.type === "ema" ? ema(closes, ma.period, i, prev) : sma(closes, ma.period, i);
      out[i][ma.key] = v;
      if (ma.type === "ema") prev = v ?? prev;
    }
  }
  return out;
}

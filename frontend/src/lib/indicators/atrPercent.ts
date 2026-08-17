// ATR% — Wilder's 14-period Average True Range as a percentage of close.
// Spec 021 FR-007. Percentage rather than raw ATR so the volatility regime is
// comparable across timeframes and across tickers at different price levels.
import type { OHLCVBar } from "../../api/types";

export const ATR_WARMUP = 15; // 14 periods + the first bar, which has no prior close

export interface AtrPoint {
  date: string;
  atrPct: number | null;
}

function trueRange(bar: OHLCVBar, prevClose: number): number {
  return Math.max(
    bar.high - bar.low,
    Math.abs(bar.high - prevClose),
    Math.abs(bar.low - prevClose),
  );
}

export function computeAtrPercent(bars: OHLCVBar[], period = 14): AtrPoint[] {
  const out: AtrPoint[] = bars.map((b) => ({ date: b.date, atrPct: null }));
  if (bars.length <= period) return out;

  const trs: number[] = [];
  for (let i = 1; i < bars.length; i++) trs.push(trueRange(bars[i], bars[i - 1].close));

  // Seed with a simple average of the first `period` true ranges, then smooth
  // the Wilder way: atr = (prev * (n-1) + tr) / n.
  let atr = trs.slice(0, period).reduce((a, v) => a + v, 0) / period;
  const seedIndex = period; // bars index whose TR closed the seed window
  out[seedIndex] = {
    date: bars[seedIndex].date,
    atrPct: bars[seedIndex].close ? (atr / bars[seedIndex].close) * 100 : null,
  };

  for (let i = period + 1; i < bars.length; i++) {
    atr = (atr * (period - 1) + trs[i - 1]) / period;
    out[i] = { date: bars[i].date, atrPct: bars[i].close ? (atr / bars[i].close) * 100 : null };
  }
  return out;
}

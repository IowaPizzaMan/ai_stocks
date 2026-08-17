// MACD (12/26/9) — spec 021 FR-007. Not rendered on the yearly panel: the
// 9-period signal on top of a 26-period EMA needs ~35 bars of warm-up, i.e.
// ~35 years of yearly candles, which essentially no ticker has.
import type { OHLCVBar } from "../../api/types";

export const MACD_WARMUP = 35;

export interface MacdPoint {
  date: string;
  macd: number | null;
  signal: number | null;
  histogram: number | null;
}

/** EMA series seeded with the SMA of the first `period` values, null before that. */
function emaSeries(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null);
  if (values.length < period) return out;
  const k = 2 / (period + 1);
  let sum = 0;
  for (let i = 0; i < period; i++) sum += values[i];
  let prev = sum / period;
  out[period - 1] = prev;
  for (let i = period; i < values.length; i++) {
    prev = values[i] * k + prev * (1 - k);
    out[i] = prev;
  }
  return out;
}

export function computeMacd(
  bars: OHLCVBar[],
  fast = 12,
  slow = 26,
  signalPeriod = 9,
): MacdPoint[] {
  const closes = bars.map((b) => b.close);
  const fastEma = emaSeries(closes, fast);
  const slowEma = emaSeries(closes, slow);

  const macdLine: (number | null)[] = closes.map((_, i) =>
    fastEma[i] != null && slowEma[i] != null ? (fastEma[i] as number) - (slowEma[i] as number) : null,
  );

  // The signal EMA runs over the MACD line only from where it exists.
  const firstMacd = macdLine.findIndex((v) => v != null);
  const signalLine: (number | null)[] = new Array(closes.length).fill(null);
  if (firstMacd !== -1) {
    const dense = macdLine.slice(firstMacd) as number[];
    const denseSignal = emaSeries(dense, signalPeriod);
    denseSignal.forEach((v, i) => {
      signalLine[firstMacd + i] = v;
    });
  }

  return bars.map((b, i) => ({
    date: b.date,
    macd: macdLine[i],
    signal: signalLine[i],
    histogram:
      macdLine[i] != null && signalLine[i] != null
        ? (macdLine[i] as number) - (signalLine[i] as number)
        : null,
  }));
}

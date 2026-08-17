// Stochastic oscillator %K(14)/%D(3) — spec 021 FR-007. Where price closed
// within its recent high-low range: overbought >80, oversold <20.
import type { OHLCVBar } from "../../api/types";

export const STOCHASTIC_WARMUP = 14;
export const OVERBOUGHT = 80;
export const OVERSOLD = 20;

export interface StochasticPoint {
  date: string;
  k: number | null;
  d: number | null;
}

export function computeStochastic(
  bars: OHLCVBar[],
  kPeriod = 14,
  dPeriod = 3,
): StochasticPoint[] {
  const kValues: (number | null)[] = bars.map((b, i) => {
    if (i + 1 < kPeriod) return null;
    const window = bars.slice(i + 1 - kPeriod, i + 1);
    const high = Math.max(...window.map((w) => w.high));
    const low = Math.min(...window.map((w) => w.low));
    // A flat range means no positional information — treat as mid-range
    // rather than dividing by zero.
    if (high === low) return 50;
    const raw = ((b.close - low) / (high - low)) * 100;
    return Math.min(100, Math.max(0, raw));
  });

  return bars.map((b, i) => {
    let d: number | null = null;
    if (i + 1 >= kPeriod + dPeriod - 1) {
      const window = kValues.slice(i + 1 - dPeriod, i + 1);
      if (window.every((v) => v != null)) {
        d = (window as number[]).reduce((a, v) => a + v, 0) / dPeriod;
      }
    }
    return { date: b.date, k: kValues[i], d };
  });
}

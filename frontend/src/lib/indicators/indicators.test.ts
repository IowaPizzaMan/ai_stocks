import { describe, expect, test } from "vitest";
import type { OHLCVBar } from "../../api/types";
import { ATR_WARMUP, computeAtrPercent } from "./atrPercent";
import { MACD_WARMUP, computeMacd } from "./macd";
import { OVERBOUGHT, OVERSOLD, STOCHASTIC_WARMUP, computeStochastic } from "./stochastic";
import { ZSCORE_WARMUP, computeZScore } from "./zscore";

/** Bars with an explicit close series; OHLC derived around it. */
function bars(closes: number[], spread = 1): OHLCVBar[] {
  return closes.map((close, i) => ({
    date: `2026-01-${String(i + 1).padStart(2, "0")}`,
    open: close,
    high: close + spread,
    low: close - spread,
    close,
    volume: 1000,
  }));
}

const rising = (n: number, start = 100) =>
  bars(Array.from({ length: n }, (_, i) => start + i));

describe("MACD", () => {
  test("is null early and fully defined by the declared warm-up", () => {
    const out = computeMacd(rising(60));
    expect(out).toHaveLength(60);
    expect(out[0].macd).toBeNull();
    expect(out[0].signal).toBeNull();
    // MACD_WARMUP is what IndicatorPanel gates on, so a series of exactly that
    // length must already produce a complete reading.
    const atWarmup = computeMacd(rising(MACD_WARMUP));
    expect(atWarmup[MACD_WARMUP - 1].macd).not.toBeNull();
    expect(atWarmup[MACD_WARMUP - 1].signal).not.toBeNull();
    expect(atWarmup[MACD_WARMUP - 1].histogram).not.toBeNull();
  });

  test("histogram equals macd minus signal wherever both exist", () => {
    const out = computeMacd(rising(60));
    for (const p of out) {
      if (p.macd != null && p.signal != null) {
        expect(p.histogram).toBeCloseTo(p.macd - p.signal, 10);
      } else {
        expect(p.histogram).toBeNull();
      }
    }
  });

  test("a steadily rising series produces a positive MACD line", () => {
    const out = computeMacd(rising(80));
    expect(out[out.length - 1].macd).toBeGreaterThan(0);
  });

  test("a steadily falling series produces a negative MACD line", () => {
    const out = computeMacd(bars(Array.from({ length: 80 }, (_, i) => 200 - i)));
    expect(out[out.length - 1].macd).toBeLessThan(0);
  });

  test("returns all-null rather than throwing on short history", () => {
    const out = computeMacd(rising(10));
    expect(out.every((p) => p.macd === null && p.signal === null)).toBe(true);
  });
});

describe("Stochastic", () => {
  test("%K is null through the warm-up", () => {
    const out = computeStochastic(rising(30));
    expect(out[STOCHASTIC_WARMUP - 2].k).toBeNull();
    expect(out[STOCHASTIC_WARMUP - 1].k).not.toBeNull();
  });

  test("all values stay within 0-100", () => {
    const noisy = bars([
      100, 104, 99, 108, 95, 112, 90, 118, 88, 121, 85, 125, 82, 130, 80, 133, 78, 137, 75, 140,
    ]);
    for (const p of computeStochastic(noisy)) {
      if (p.k != null) {
        expect(p.k).toBeGreaterThanOrEqual(0);
        expect(p.k).toBeLessThanOrEqual(100);
      }
      if (p.d != null) {
        expect(p.d).toBeGreaterThanOrEqual(0);
        expect(p.d).toBeLessThanOrEqual(100);
      }
    }
  });

  test("closing at the top of the range reads overbought, bottom reads oversold", () => {
    const up = computeStochastic(rising(30));
    expect(up[up.length - 1].k).toBeGreaterThan(OVERBOUGHT);

    const down = computeStochastic(bars(Array.from({ length: 30 }, (_, i) => 200 - i)));
    expect(down[down.length - 1].k).toBeLessThan(OVERSOLD);
  });

  test("a flat range reads mid-scale instead of dividing by zero", () => {
    const flat = bars(new Array(20).fill(100), 0);
    const out = computeStochastic(flat);
    expect(out[out.length - 1].k).toBe(50);
    expect(Number.isFinite(out[out.length - 1].k as number)).toBe(true);
  });

  test("%D is the 3-period average of %K", () => {
    const out = computeStochastic(rising(30));
    const i = out.length - 1;
    const window = [out[i - 2].k, out[i - 1].k, out[i].k] as number[];
    expect(out[i].d).toBeCloseTo((window[0] + window[1] + window[2]) / 3, 10);
  });
});

describe("ATR%", () => {
  test("is null through the warm-up and defined after it", () => {
    const out = computeAtrPercent(rising(40));
    expect(out[ATR_WARMUP - 2].atrPct).toBeNull();
    expect(out[out.length - 1].atrPct).not.toBeNull();
  });

  test("a constant true range yields a stable, correctly scaled percentage", () => {
    // close constant at 100, high/low ±1 → true range 2 → ATR 2 → 2% of price
    const flat = bars(new Array(40).fill(100), 1);
    const out = computeAtrPercent(flat);
    expect(out[out.length - 1].atrPct).toBeCloseTo(2, 6);
  });

  test("a wider range produces a higher ATR%", () => {
    const narrow = computeAtrPercent(bars(new Array(40).fill(100), 1));
    const wide = computeAtrPercent(bars(new Array(40).fill(100), 4));
    expect(wide[39].atrPct as number).toBeGreaterThan(narrow[39].atrPct as number);
  });

  test("returns all-null rather than throwing on short history", () => {
    expect(computeAtrPercent(rising(5)).every((p) => p.atrPct === null)).toBe(true);
  });
});

describe("Z-score", () => {
  test("is null through the warm-up and defined after it", () => {
    const out = computeZScore(rising(30));
    expect(out[ZSCORE_WARMUP - 2].zscore).toBeNull();
    expect(out[ZSCORE_WARMUP - 1].zscore).not.toBeNull();
  });

  test("a close above its recent mean is positive, below is negative", () => {
    const up = computeZScore(rising(30));
    expect(up[up.length - 1].zscore as number).toBeGreaterThan(0);

    const down = computeZScore(bars(Array.from({ length: 30 }, (_, i) => 200 - i)));
    expect(down[down.length - 1].zscore as number).toBeLessThan(0);
  });

  test("a flat window scores zero rather than dividing by zero", () => {
    const out = computeZScore(bars(new Array(25).fill(100)));
    expect(out[out.length - 1].zscore).toBe(0);
  });

  test("matches a hand-computed z-score", () => {
    // last 20 closes are 1..20: mean 10.5, population sd ~5.7663, close 20
    const out = computeZScore(bars(Array.from({ length: 20 }, (_, i) => i + 1)));
    const mean = 10.5;
    const variance =
      Array.from({ length: 20 }, (_, i) => (i + 1 - mean) ** 2).reduce((a, v) => a + v, 0) / 20;
    expect(out[19].zscore).toBeCloseTo((20 - mean) / Math.sqrt(variance), 10);
  });
});

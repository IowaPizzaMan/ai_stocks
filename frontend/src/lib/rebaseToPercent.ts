// specs/028-dashboard-tweaks-batch US5 (FR-020, R6) — pure percentage
// rebasing so differently-priced sector ETFs share one comparable baseline
// (clarification Q2). Rebases against the first close *in the given array*,
// so a window-sliced series always starts at 0% for that window.

export interface PriceBar {
  date: string;
  close: number;
}

export interface PctPoint {
  date: string;
  pct: number;
}

export function rebaseToPercent(bars: PriceBar[]): PctPoint[] {
  if (bars.length === 0) return [];
  const first = bars[0].close;
  if (first === 0) return [];
  return bars.map((b) => ({ date: b.date, pct: ((b.close / first) - 1) * 100 }));
}

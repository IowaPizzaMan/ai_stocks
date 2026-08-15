// Spec: specs/component-specs/frontend/components/stock/PriceChart.md "Broadening Formations"
import type { OHLCVBar } from "../../api/types";

export interface BFZone {
  start: string;
  end: string;
  high: number;
  low: number;
  active: boolean;
}

function classifyBar(bar: OHLCVBar, prev: OHLCVBar): "1" | "2U" | "2D" | "3" {
  const higherHigh = bar.high > prev.high;
  const lowerLow = bar.low < prev.low;
  if (higherHigh && lowerLow) return "3";
  if (higherHigh) return "2U";
  if (lowerLow) return "2D";
  return "1";
}

/** Every Outside Bar (3) IS a broadening formation. Open a zone at each
 * outside bar, expand while price extends it, close it out on a TFC color
 * flip (former BF levels become support/resistance). Keeps the last 4. */
export function detectBroadeningFormations(bars: OHLCVBar[]): BFZone[] {
  const zones: BFZone[] = [];
  let current: BFZone | null = null;
  let lastColor: "green" | "red" | null = null;

  for (let i = 1; i < bars.length; i++) {
    const bar = bars[i];
    const type = classifyBar(bar, bars[i - 1]);
    const color = bar.close >= bar.open ? "green" : "red";

    if (type === "3") {
      if (current) {
        current.active = false;
        zones.push(current);
      }
      current = { start: bar.date, end: bar.date, high: bar.high, low: bar.low, active: true };
    } else if (current) {
      if (bar.high > current.high) current.high = bar.high;
      if (bar.low < current.low) current.low = bar.low;
      current.end = bar.date;
    }

    if (current && lastColor && color !== lastColor && type !== "3") {
      current.end = bar.date;
      zones.push({ ...current, active: false });
      current = { start: bar.date, end: bar.date, high: bar.high, low: bar.low, active: true };
    }
    lastColor = color;
  }

  if (current) zones.push(current);
  return zones.slice(-4);
}

/** Detection ran on full history; clip zones to the visible window so
 * reference areas don't draw outside the chart's x-domain. */
export function clipZonesToDisplayWindow(zones: BFZone[], visible: OHLCVBar[]): BFZone[] {
  if (!visible.length) return [];
  const windowStart = visible[0].date;
  const windowEnd = visible[visible.length - 1].date;

  return zones
    .filter((z) => z.end >= windowStart)
    .map((z) => ({
      ...z,
      start: z.start < windowStart ? windowStart : z.start,
      end: z.active ? windowEnd : z.end > windowEnd ? windowEnd : z.end,
    }));
}

export const CHART_DEFAULTS = {
  textColor: "#71717a", // zinc-500
  accentColor: "#38bdf8", // sky-400
  volumeColor: "#3f3f46", // zinc-700
  bullishColor: "#34d399", // emerald-400
  bearishColor: "#f87171", // red-400
  warningColor: "#fbbf24", // amber-400
  bfActiveColor: "#a78bfa", // violet-400
  bfPriorColor: "#52525b", // zinc-600
  gridColor: "#27272a", // zinc-800
};

// Metric heat-scale ranges for MetricCard (spec: shared/MetricCard.md).
// Keys are the real FMP field names served by /stocks/{ticker}/financials.
// The scale is pure magnitude — low raw value is always ice blue, high is
// always red — independent of whether "high" is good for that ratio; the
// label carries the meaning, the color just says where the number sits.
// FMP reports margin/yield/returns ratios as fractions (0.46 = 46%), so
// 'pct' ranges are in fraction units and the formatter multiplies by 100.
export type MetricKey =
  | "priceToEarningsRatio"
  | "enterpriseValueMultiple"
  | "freeCashFlowYield"
  | "debtToEquityRatio"
  | "grossProfitMargin"
  | "returnOnEquity"
  | "returnOnInvestedCapital";

export const METRIC_RANGES: Record<MetricKey, { min: number; max: number; format: "pct" | "x" }> = {
  priceToEarningsRatio: { min: 5, max: 60, format: "x" }, // <8 ice blue, >45 red
  enterpriseValueMultiple: { min: 4, max: 30, format: "x" },
  freeCashFlowYield: { min: -0.05, max: 0.15, format: "pct" },
  debtToEquityRatio: { min: 0, max: 3, format: "x" },
  grossProfitMargin: { min: 0.1, max: 0.8, format: "pct" },
  returnOnEquity: { min: -0.1, max: 0.4, format: "pct" },
  returnOnInvestedCapital: { min: -0.1, max: 0.4, format: "pct" },
};

export interface MetricBand {
  bg: string;
  text: string;
  border: string;
}

const BANDS: ({ max: number } & MetricBand)[] = [
  { max: 0.2, bg: "bg-sky-500/15", text: "text-sky-300", border: "border-sky-500/30" }, // ice blue — low end
  { max: 0.4, bg: "bg-cyan-500/10", text: "text-cyan-300", border: "border-cyan-500/20" },
  { max: 0.6, bg: "bg-zinc-800", text: "text-zinc-300", border: "border-zinc-700" }, // neutral — mid range
  { max: 0.8, bg: "bg-amber-500/15", text: "text-amber-400", border: "border-amber-500/30" },
  { max: 1.01, bg: "bg-red-500/15", text: "text-red-400", border: "border-red-500/30" }, // hot — high end
];

export function getMetricBand(metricKey: MetricKey, value: number | null | undefined): MetricBand {
  if (value == null) return BANDS[2]; // no data → neutral
  const { min, max } = METRIC_RANGES[metricKey];
  const pct = Math.min(Math.max((value - min) / (max - min), 0), 1);
  return BANDS.find((b) => pct <= b.max)!;
}

export function formatMetric(metricKey: MetricKey, value: number | null | undefined): string {
  if (value == null) return "—";
  const { format } = METRIC_RANGES[metricKey];
  return format === "pct" ? `${(value * 100).toFixed(1)}%` : `${value.toFixed(1)}x`;
}

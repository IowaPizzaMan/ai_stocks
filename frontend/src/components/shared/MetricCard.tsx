// Single metric tile colored by where the value sits in that metric's typical
// range — ice blue (low) → red (high). Spec: shared/MetricCard.md.
import { formatMetric, getMetricBand, type MetricKey } from "../../lib/constants";
import TrendArrow from "./TrendArrow";

export default function MetricCard({
  metricKey,
  label,
  value,
  trend,
  caption,
}: {
  metricKey: MetricKey;
  label: string;
  value: number | null | undefined;
  trend?: "up" | "down" | "flat";
  caption?: string;
}) {
  const band = getMetricBand(metricKey, value);
  return (
    <div className={`rounded-xl border p-4 ${band.bg} ${band.border}`}>
      <div className="mb-1 text-xs text-zinc-400">{label}</div>
      <div className="flex items-baseline gap-2">
        <span className={`text-2xl font-semibold ${band.text}`}>
          {formatMetric(metricKey, value)}
        </span>
        {trend && <TrendArrow direction={trend} className="text-xs opacity-70" />}
      </div>
      {caption && <p className="mt-1 text-[11px] leading-snug text-zinc-500">{caption}</p>}
    </div>
  );
}

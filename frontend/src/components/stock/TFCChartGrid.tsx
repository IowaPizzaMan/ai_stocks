// Spec: specs/component-specs/frontend/components/stock/TFCChartGrid.md (via StockDetail.md)
// Four compact panels (1D/1W/1M/1Y) with BF overlays + a Full TFC banner.
import type { OHLCVBar } from "../../api/types";
import type { Timeframe } from "../../lib/strat/displayWindow";
import PriceChart from "./PriceChart";

const PANELS: Timeframe[] = ["1D", "1W", "1M", "1Y"];

const BANNER: Record<string, { text: string; className: string }> = {
  full_bullish: {
    text: "Full TFC — bullish: all participation groups are aligned green",
    className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  },
  full_bearish: {
    text: "Full TFC — bearish: all participation groups are aligned red",
    className: "border-red-500/30 bg-red-500/10 text-red-400",
  },
  conflict: {
    text: "TFC in conflict — participation groups disagree; expect chop",
    className: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  },
};

export default function TFCChartGrid({
  priceData,
  tfcStatus,
}: {
  priceData: Partial<Record<Timeframe, OHLCVBar[]>>;
  tfcStatus?: string;
}) {
  const banner = tfcStatus ? BANNER[tfcStatus] : undefined;

  return (
    <div>
      {banner && (
        <div className={`mb-3 rounded-lg border px-3 py-2 text-sm ${banner.className}`}>
          {banner.text}
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        {PANELS.map((tf) => (
          <div key={tf} className="rounded-xl border border-zinc-800 bg-zinc-900 p-3">
            <p className="mb-1 text-xs font-medium text-zinc-400">{tf}</p>
            <PriceChart
              priceData={priceData[tf] ?? []}
              defaultTimeframe={tf}
              compact
              showMovingAverages={false}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

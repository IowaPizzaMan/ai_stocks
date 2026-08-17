// Spec: specs/021-stock-page-redesign US1/US2/US3 (FR-001..FR-009)
// The page's only chart surface: four resolution-true candlestick panels
// (daily/weekly/monthly/yearly), then price/volume ROC, then the per-timeframe
// indicator grid. Renders from price data alone — no analysis required (FR-009).
import type { OHLCVBar } from "../../api/types";
import {
  PANEL_LABELS,
  PANEL_TIMEFRAMES,
  sliceForDisplay,
  type Timeframe,
} from "../../lib/strat/displayWindow";
import CandlestickChart from "./CandlestickChart";
import IndicatorPanel from "./IndicatorPanel";
import RateOfChangeChart from "./RateOfChangeChart";

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

export default function ChartsTab({
  priceData,
  tfcStatus,
}: {
  priceData: Partial<Record<Timeframe, OHLCVBar[]>>;
  tfcStatus?: string;
}) {
  const banner = tfcStatus ? BANNER[tfcStatus] : undefined;
  // ROC reads the daily panel's window — bar-over-bar change is only
  // meaningful at a single resolution, and daily is the one users act on.
  const dailyBars = sliceForDisplay(priceData.D ?? [], "D", false);

  return (
    <div className="space-y-4">
      {banner && (
        <div className={`rounded-lg border px-3 py-2 text-sm ${banner.className}`}>{banner.text}</div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {PANEL_TIMEFRAMES.map((tf) => (
          <div key={tf} className="rounded-xl border border-zinc-800 bg-zinc-900 p-3">
            <p className="mb-1 text-xs font-medium text-zinc-400">{PANEL_LABELS[tf]}</p>
            <CandlestickChart bars={priceData[tf] ?? []} timeframe={tf} />
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Rate of change — daily
        </h2>
        {dailyBars.length ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <RateOfChangeChart bars={dailyBars} metric="price" />
            <RateOfChangeChart bars={dailyBars} metric="volume" />
          </div>
        ) : (
          <p className="py-4 text-center text-xs text-zinc-600">no price data</p>
        )}
      </div>

      <div className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">Indicators</h2>
        <IndicatorPanel indicator="zscore" priceData={priceData} />
        <IndicatorPanel indicator="stochastic" priceData={priceData} />
        <IndicatorPanel indicator="atrPercent" priceData={priceData} />
        <IndicatorPanel indicator="macd" priceData={priceData} />
      </div>
    </div>
  );
}

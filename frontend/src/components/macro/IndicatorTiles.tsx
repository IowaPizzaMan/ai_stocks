// Spec: specs/026-macro-market-dashboard/contracts/macro-api.md
//
// Headline growth/inflation/employment/policy-rate readings, plus the US
// equity risk premium. Direction is shown as a plain fact (▲/▼/→), not
// colored good/bad — the same reasoning as the economic calendar's neutral
// comparison labels (FR-021b): "up" is good for GDP and bad for unemployment,
// so any single color mapping would silently assert a judgment call this
// page deliberately does not make.
import type { IndicatorTile as IndicatorTileData, RiskPremium } from "../../api/types";

const DIRECTION_GLYPH: Record<NonNullable<IndicatorTileData["direction"]>, string> = {
  up: "▲",
  down: "▼",
  flat: "→",
};

function IndicatorCard({ tile }: { tile: IndicatorTileData }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wide text-zinc-500">{tile.label}</p>
        {tile.lagging && (
          <span className="rounded-full border border-zinc-700 px-1.5 py-0.5 text-[10px] uppercase text-zinc-500">
            lagging
          </span>
        )}
      </div>
      <p className="mt-1 text-xl font-semibold text-white">
        {tile.value.toLocaleString()}
        {tile.unit}
        {tile.direction && (
          <span className="ml-2 text-sm text-zinc-500">{DIRECTION_GLYPH[tile.direction]}</span>
        )}
      </p>
      <p className="text-xs text-zinc-500">as of {tile.as_of}</p>
    </div>
  );
}

function RiskPremiumCard({ data }: { data: RiskPremium }) {
  if (data.total_equity_risk_premium == null) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3">
        <p className="text-xs uppercase tracking-wide text-zinc-500">US equity risk premium</p>
        <p className="mt-1 text-sm text-zinc-600">not available yet</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3">
      <p className="text-xs uppercase tracking-wide text-zinc-500">US equity risk premium</p>
      <p className="mt-1 text-xl font-semibold text-white">
        {data.total_equity_risk_premium.toFixed(2)}%
      </p>
      <p className="text-xs text-zinc-500">slow-moving valuation input, not a live market quote</p>
    </div>
  );
}

export default function IndicatorTiles({
  indicators,
  riskPremium,
}: {
  indicators: IndicatorTileData[];
  riskPremium?: RiskPremium;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      {indicators.map((tile) => (
        <IndicatorCard key={tile.key} tile={tile} />
      ))}
      {riskPremium && <RiskPremiumCard data={riskPremium} />}
    </div>
  );
}

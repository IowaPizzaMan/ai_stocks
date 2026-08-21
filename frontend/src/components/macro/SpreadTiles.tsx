// Spec: specs/026-macro-market-dashboard/contracts/macro-api.md
//
// The three tracked spreads (10y-2y, 30y-10y, 10y-3m): current value, change
// vs. the prior session, an inversion badge, and a small trend sparkline.
// All arithmetic (bps, change, inverted, trend series) is computed server
// side (data-model.md §6) — this only formats and lays it out.
import { Line, LineChart, ResponsiveContainer } from "recharts";
import type { Spread } from "../../api/types";
import { CHART_DEFAULTS } from "../../lib/constants";
import { formatBps, formatChange, hasSpreadData } from "../../lib/yieldCurve";

function SpreadTile({ spread }: { spread: Spread }) {
  if (!hasSpreadData(spread)) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3">
        <p className="text-xs uppercase tracking-wide text-zinc-600">{spread.label}</p>
        <p className="mt-1 text-sm text-zinc-600">not available yet</p>
      </div>
    );
  }

  const lineColor = spread.inverted ? CHART_DEFAULTS.warningColor : CHART_DEFAULTS.bullishColor;

  return (
    <div
      className={`rounded-lg border p-3 ${
        spread.inverted ? "border-amber-500/30 bg-amber-500/5" : "border-zinc-800 bg-zinc-950"
      }`}
    >
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wide text-zinc-500">{spread.label}</p>
        {spread.inverted && (
          <span className="rounded-full border border-amber-500/40 px-1.5 py-0.5 text-[10px] uppercase text-amber-400">
            inverted
          </span>
        )}
      </div>
      <p className="mt-1 text-xl font-semibold text-white">{formatBps(spread.current_bps)}</p>
      <p className="text-xs text-zinc-500">{formatChange(spread.change_bps)}</p>
      {spread.series.length > 1 && (
        <ResponsiveContainer width="100%" height={32}>
          <LineChart data={spread.series} margin={{ top: 4, right: 2, bottom: 0, left: 2 }}>
            <Line
              type="monotone"
              dataKey="bps"
              stroke={lineColor}
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

export default function SpreadTiles({ spreads }: { spreads: Spread[] }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {spreads.map((spread) => (
        <SpreadTile key={spread.key} spread={spread} />
      ))}
    </div>
  );
}

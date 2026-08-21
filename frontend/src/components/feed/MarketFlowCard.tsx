// Spec: specs/component-specs/frontend/components/stock/BreadthDivergenceChart.md
//        ("Market-flow feed card")
//
// Breadth divergences are market-wide, so they have no ticker to hang off and
// can't ride the per-ticker analysis feed. These pin above it instead.
//
// The Macro page (specs/026-macro-market-dashboard, FR-002a) renders this
// card as the page's one permanent breadth panel, not just as an event-pinned
// feed item — so `event` is optional. With an event it looks as it always
// has (tinted outline, headline, body). With none, it's a neutral breadth
// panel: no headline row, no divergence-colored border, but the chart and
// divergence caption still render from `breadth` alone.
import type { MarketBreadth, MarketFlowEvent } from "../../api/types";
import { relativeTime } from "../../lib/time";
import BreadthDivergenceChart from "../stock/BreadthDivergenceChart";

const TONE = {
  bullish: "border-emerald-500/30 bg-emerald-500/5",
  bearish: "border-amber-500/30 bg-amber-500/5",
  neutral: "border-zinc-800",
} as const;

export default function MarketFlowCard({
  event,
  breadth,
}: {
  event?: MarketFlowEvent;
  breadth?: MarketBreadth;
}) {
  const tone = event ? TONE[event.divergence_type] : TONE.neutral;

  return (
    <article className={`rounded-xl border p-5 ${tone}`}>
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="rounded-full border border-zinc-700 px-2.5 py-0.5 text-[11px] uppercase tracking-wide text-zinc-400">
            market flow
          </span>
          {event ? (
            <span className="text-sm font-semibold text-white">{event.headline}</span>
          ) : (
            <span className="text-sm font-semibold text-white">Market breadth</span>
          )}
        </div>
        {event && <span className="text-xs text-zinc-500">{relativeTime(event.created_at)}</span>}
      </div>

      {event && (
        <p className="mb-3 text-sm text-zinc-300">
          {event.body}
          {event.nymo_current != null && (
            <span className="text-zinc-500"> · NYMO {event.nymo_current}</span>
          )}
        </p>
      )}

      {breadth && <BreadthDivergenceChart breadth={breadth} compact />}
    </article>
  );
}

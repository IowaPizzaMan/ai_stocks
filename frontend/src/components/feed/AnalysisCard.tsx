// Spec: specs/component-specs/frontend/components/feed/AnalysisCard.md
import { useNavigate } from "react-router-dom";
import type { AnalysisFeedItem } from "../../api/types";
import { useAddToWatchlist } from "../../hooks/useWatchlist";
import { relativeTime } from "../../lib/time";
import ConvictionMeter from "../shared/ConvictionMeter";
import SignalBadge from "../shared/SignalBadge";

const INSTITUTIONAL_FLAG: Record<string, { label: string; className: string }> = {
  buying: { label: "↑ Institutions buying", className: "border-emerald-500/30 text-emerald-400" },
  selling: { label: "↓ Institutions selling", className: "border-red-500/30 text-red-400" },
  mixed: { label: "Institutions mixed", className: "border-zinc-700 text-zinc-400" },
};

export default function AnalysisCard({ analysis }: { analysis: AnalysisFeedItem }) {
  const navigate = useNavigate();
  const addToWatchlist = useAddToWatchlist();
  const instFlag = analysis.recent_institutional_activity
    ? INSTITUTIONAL_FLAG[analysis.recent_institutional_activity]
    : undefined;

  return (
    <article
      className="cursor-pointer rounded-xl border border-zinc-800 bg-zinc-900 p-5 transition-all hover:border-zinc-700 hover:bg-zinc-800/50"
      onClick={() => navigate(`/stock/${analysis.ticker}`)}
    >
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold text-white">{analysis.ticker}</span>
          <SignalBadge signal={analysis.signal} />
          {analysis.sector && (
            <span className="text-xs text-zinc-500">{analysis.sector}</span>
          )}
        </div>
        <span className="text-xs text-zinc-500">{relativeTime(analysis.timestamp)}</span>
      </div>

      <p className="mb-4 line-clamp-3 text-sm leading-relaxed text-zinc-300">
        {analysis.summary}
      </p>

      {analysis.flags.length > 0 && (
        <p className="mb-3 text-xs text-amber-400">⚑ {analysis.flags[0]}</p>
      )}

      {(instFlag || analysis.recent_insider_summary) && (
        <div className="mb-3 flex flex-wrap gap-2">
          {instFlag && (
            <span className={`rounded-full border px-2.5 py-0.5 text-xs ${instFlag.className}`}>
              {instFlag.label}
            </span>
          )}
          {analysis.recent_insider_summary && (
            <span className="rounded-full border border-zinc-700 px-2.5 py-0.5 text-xs text-zinc-400">
              insiders: {analysis.recent_insider_summary}
            </span>
          )}
        </div>
      )}

      <div className="flex items-center justify-between">
        <ConvictionMeter conviction={analysis.conviction} label />
        <button
          className="text-xs text-zinc-500 transition-colors hover:text-zinc-300"
          onClick={(e) => {
            e.stopPropagation();
            addToWatchlist.mutate(analysis.ticker);
          }}
        >
          + Watchlist
        </button>
      </div>
    </article>
  );
}

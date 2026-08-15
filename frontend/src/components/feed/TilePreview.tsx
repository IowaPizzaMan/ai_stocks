// Spec: specs/component-specs/frontend/components/feed/AnalysisTile.md ("TilePreview")
import type { AnalysisFeedItem } from "../../api/types";
import { useAddToWatchlist } from "../../hooks/useWatchlist";
import { formatDate, relativeTime } from "../../lib/time";
import ConvictionMeter from "../shared/ConvictionMeter";
import SignalBadge from "../shared/SignalBadge";

export default function TilePreview({ analysis }: { analysis: AnalysisFeedItem }) {
  const addToWatchlist = useAddToWatchlist();
  const dataAsOf = formatDate(analysis.timestamp);

  return (
    <div
      role="tooltip"
      className="w-64 rounded-lg border border-zinc-700 bg-zinc-900 p-3 text-left shadow-xl"
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <SignalBadge signal={analysis.signal} />
        <span className="text-right text-[11px] leading-tight text-zinc-500">
          <span className="block">{relativeTime(analysis.timestamp)}</span>
          {dataAsOf && <span className="block">data as of {dataAsOf}</span>}
        </span>
      </div>

      <p className="mb-3 line-clamp-3 text-xs leading-relaxed text-zinc-300">
        {analysis.summary}
      </p>

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
    </div>
  );
}

// Spec: specs/component-specs/frontend/components/feed/AnalysisTile.md ("TilePreview")
// specs/029-company-profile-tweaks US3 (FR-020/FR-021/FR-021a/FR-023): shows
// the stock's full AI summary (no truncation), plus its logo and company
// name, now that the Portfolio Summary panel is gone — this card is the
// per-stock place the user reads the AI's take.
import type { AnalysisFeedItem } from "../../api/types";
import { useAddToWatchlist } from "../../hooks/useWatchlist";
import { formatDate, relativeTime } from "../../lib/time";
import CompanyLogo from "../shared/CompanyLogo";
import ConvictionMeter from "../shared/ConvictionMeter";
import SignalBadge from "../shared/SignalBadge";

export default function TilePreview({ analysis }: { analysis: AnalysisFeedItem }) {
  const addToWatchlist = useAddToWatchlist();
  const dataAsOf = formatDate(analysis.timestamp);

  return (
    <div
      role="tooltip"
      className="max-h-80 w-64 overflow-y-auto rounded-lg border border-zinc-700 bg-zinc-900 p-3 text-left shadow-xl"
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <CompanyLogo ticker={analysis.ticker} src={analysis.logo_url} size="sm" />
          {analysis.name && <span className="text-xs text-zinc-400">{analysis.name}</span>}
        </div>
        <SignalBadge signal={analysis.signal} />
      </div>

      <div className="mb-2 text-right text-[11px] leading-tight text-zinc-500">
        <span className="block">{relativeTime(analysis.timestamp)}</span>
        {dataAsOf && <span className="block">data as of {dataAsOf}</span>}
      </div>

      {analysis.summary ? (
        <p className="mb-3 whitespace-pre-line text-xs leading-relaxed text-zinc-300">
          {analysis.summary}
        </p>
      ) : (
        <p className="mb-3 text-xs italic text-zinc-600">No summary available.</p>
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
    </div>
  );
}

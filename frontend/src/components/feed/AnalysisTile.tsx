// Spec: specs/component-specs/frontend/components/feed/AnalysisTile.md
import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { AnalysisFeedItem, Conviction, Signal } from "../../api/types";
import { useDeleteTicker } from "../../hooks/useAnalysis";
import { relativeTime } from "../../lib/time";
import RemoveIcon from "../shared/RemoveIcon";
import RemoveTickerConfirm from "./RemoveTickerConfirm";
import TilePreview from "./TilePreview";

const FILL: Record<Signal, string> = {
  bullish: "border-emerald-500/30 bg-emerald-500/15 text-emerald-400",
  bearish: "border-red-500/30 bg-red-500/15 text-red-400",
  neutral: "border-zinc-500/30 bg-zinc-500/15 text-zinc-300",
};
const FALLBACK_FILL = "border-dashed border-zinc-700 bg-transparent text-zinc-500";

const CONVICTION_LEVEL: Record<Conviction, number> = { high: 3, medium: 2, low: 1 };

// Rough preview footprint (w-64 + padding) used to decide whether it needs to
// flip toward the tile's other edge instead of overflowing the viewport.
const PREVIEW_WIDTH_PX = 260;
const PREVIEW_HEIGHT_PX = 160;

function isKnownSignal(signal: AnalysisFeedItem["signal"]): signal is Signal {
  return signal in FILL;
}

function convictionLevel(conviction: AnalysisFeedItem["conviction"]): number {
  return CONVICTION_LEVEL[conviction as Conviction] ?? 0;
}

function buildAriaLabel(analysis: AnalysisFeedItem): string {
  const { ticker, signal, conviction } = analysis;
  const level = convictionLevel(conviction);
  const signalText = isKnownSignal(signal) ? signal : "unknown signal";
  const convictionText = level > 0 ? `${conviction} conviction (${level} of 3)` : "no conviction data";
  const recency = relativeTime(analysis.timestamp);

  const label = `${ticker} — ${signalText}, ${convictionText}`;
  return recency ? `${label}, analyzed ${recency}` : label;
}

export default function AnalysisTile({ analysis }: { analysis: AnalysisFeedItem }) {
  const navigate = useNavigate();
  const deleteMutation = useDeleteTicker();
  const tileRef = useRef<HTMLDivElement>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [placement, setPlacement] = useState<{ x: "left" | "right"; y: "top" | "bottom" }>({
    x: "left",
    y: "bottom",
  });

  const openPreview = useCallback(() => {
    const rect = tileRef.current?.getBoundingClientRect();
    if (rect) {
      setPlacement({
        x: rect.left + PREVIEW_WIDTH_PX > window.innerWidth ? "right" : "left",
        y: rect.bottom + PREVIEW_HEIGHT_PX > window.innerHeight ? "top" : "bottom",
      });
    }
    setPreviewOpen(true);
  }, []);
  const closePreview = useCallback(() => setPreviewOpen(false), []);

  const goToDetail = useCallback(
    () => navigate(`/stock/${analysis.ticker}`),
    [navigate, analysis.ticker],
  );

  const fillClass = isKnownSignal(analysis.signal) ? FILL[analysis.signal] : FALLBACK_FILL;
  const level = convictionLevel(analysis.conviction);
  const tickerSizeClass = analysis.ticker.length > 5 ? "text-[10px]" : "text-[13px]";
  const flyoutPositionClass = [
    placement.y === "top" ? "bottom-full mb-1" : "top-full mt-1",
    placement.x === "right" ? "right-0" : "left-0",
  ].join(" ");

  return (
    <div
      ref={tileRef}
      role="button"
      tabIndex={0}
      className={`relative flex h-14 cursor-pointer flex-col items-center justify-center gap-1 rounded-md border px-1 transition-colors ${fillClass}`}
      aria-label={buildAriaLabel(analysis)}
      onClick={goToDetail}
      onKeyDown={(e) => {
        if (e.key === "Enter") goToDetail();
      }}
      onMouseEnter={openPreview}
      onMouseLeave={closePreview}
      onFocus={openPreview}
      onBlur={closePreview}
    >
      <span className={`max-w-full font-semibold leading-none ${tickerSizeClass}`}>
        {analysis.ticker}
      </span>
      <span className="flex gap-1" aria-hidden="true">
        {[1, 2, 3].map((i) => (
          <span
            key={i}
            data-dot
            data-filled={i <= level}
            className={`h-1.5 w-1.5 rounded-full ${i <= level ? "bg-zinc-100" : "bg-white/10"}`}
          />
        ))}
      </span>

      {/* Delete control — a real <button>, but nested inside the tile's own
          clickable area, so both click and keydown must stop propagation to
          keep it from also triggering the tile's navigation. */}
      <button
        type="button"
        aria-label={`Delete ${analysis.ticker} and its data`}
        onClick={(e) => {
          e.stopPropagation();
          setConfirmOpen(true);
        }}
        onKeyDown={(e) => e.stopPropagation()}
        className={`absolute right-0.5 top-0.5 z-10 rounded p-0.5 text-zinc-400 transition-opacity hover:bg-black/30 hover:text-red-400 ${
          previewOpen ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      >
        <RemoveIcon className="h-3 w-3" />
      </button>

      {confirmOpen ? (
        <div className={`absolute z-20 ${flyoutPositionClass}`}>
          <RemoveTickerConfirm
            ticker={analysis.ticker}
            pending={deleteMutation.isPending}
            error={deleteMutation.isError ? `Couldn't delete ${analysis.ticker} — try again.` : null}
            onCancel={() => setConfirmOpen(false)}
            onConfirm={() =>
              deleteMutation.mutate(analysis.ticker, { onSuccess: () => setConfirmOpen(false) })
            }
          />
        </div>
      ) : (
        previewOpen && (
          <div className={`absolute z-20 ${flyoutPositionClass}`}>
            <TilePreview analysis={analysis} />
          </div>
        )
      )}
    </div>
  );
}

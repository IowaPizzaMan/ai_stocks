// Spec: specs/component-specs/frontend/components/institutional/InstitutionalFlowCard.md
// Deviation: adds a per-card Queue button (same pattern as the earnings
// calendar) — flow scans no longer auto-enqueue crew runs.
import { useNavigate } from "react-router-dom";
import type { InstitutionalFlowEvent } from "../../api/types";
import { useEnqueueTicker } from "../../hooks/useQueue";
import { relativeTime } from "../../lib/time";
import ActionBadge from "./ActionBadge";

function formatValue(valueUsd: number): string {
  if (valueUsd >= 1e9) return `$${(valueUsd / 1e9).toFixed(1)}B`;
  return `$${(valueUsd / 1e6).toFixed(1)}M`;
}

/** 5-dot meter driven by notability_score, raw score as tooltip. */
function NotabilityMeter({ score }: { score: number }) {
  const level = Math.min(5, Math.max(1, Math.ceil(score / 20)));
  const color = score >= 70 ? "bg-sky-400" : score >= 40 ? "bg-sky-600" : "bg-zinc-500";
  return (
    <span className="flex items-center gap-1.5" title={`Notability ${score}/100`}>
      <span className="flex gap-0.5">
        {[1, 2, 3, 4, 5].map((i) => (
          <span
            key={i}
            className={`h-2 w-2 rounded-full ${i <= level ? color : "bg-zinc-700"}`}
          />
        ))}
      </span>
      <span className="text-xs text-zinc-500">Notability {score}</span>
    </span>
  );
}

export default function InstitutionalFlowCard({ event }: { event: InstitutionalFlowEvent }) {
  const navigate = useNavigate();
  const enqueue = useEnqueueTicker();

  return (
    <article className="rounded-xl border border-zinc-800 bg-zinc-900 p-5 transition-all hover:border-zinc-700 hover:bg-zinc-800/50">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <ActionBadge action={event.action} />
          <span className="truncate text-sm text-zinc-300">{event.fund}</span>
          <span className="text-zinc-600">→</span>
          <button
            className="font-bold text-white hover:underline"
            onClick={() => navigate(`/stock/${event.ticker}`)}
          >
            {event.ticker}
          </button>
        </div>
        <span className="flex shrink-0 items-center gap-3">
          <span className="text-xs text-zinc-500">{relativeTime(event.filed_at)}</span>
          <button
            onClick={() => enqueue.mutate(event.ticker)}
            disabled={enqueue.isPending || enqueue.isSuccess}
            className="rounded-lg border border-zinc-700 px-2.5 py-1 text-xs text-zinc-300 transition-colors hover:border-sky-500 hover:text-sky-300 disabled:opacity-50"
          >
            {enqueue.isSuccess ? "Queued ✓" : "Queue ▶"}
          </button>
        </span>
      </div>

      <p className="mb-3 text-sm leading-relaxed text-zinc-300">{event.headline}</p>

      <div className="mb-2 flex flex-wrap items-center gap-3 text-xs text-zinc-500">
        {event.shares != null && <span>{event.shares.toLocaleString()} shares</span>}
        {event.value_usd != null && <span>{formatValue(event.value_usd)}</span>}
        {event.pct_change != null && (
          <span>
            {event.pct_change > 0 ? "+" : ""}
            {(event.pct_change * 100).toFixed(0)}% QoQ
          </span>
        )}
        {event.pct_of_portfolio != null && <span>{event.pct_of_portfolio}% of portfolio</span>}
        <span className="uppercase tracking-wide">
          {event.source === "13F" ? "13F filing" : "Dataroma"}
        </span>
      </div>

      <NotabilityMeter score={event.notability_score} />
    </article>
  );
}

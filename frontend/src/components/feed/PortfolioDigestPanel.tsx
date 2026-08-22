// Cross-stock AI summary panel on the Stocks page's default tab — specs/027.
//
// Synthesizes every tracked stock's existing AI analysis into an overview
// plus specific guidance, with a manual regenerate control. Busy state comes
// from the existing queue-status mechanism (research.md R7) — no new polling.
import { Link } from "react-router-dom";
import type { Conviction, Signal } from "../../api/types";
import ConvictionMeter from "../shared/ConvictionMeter";
import SignalBadge from "../shared/SignalBadge";
import FormattedProse from "../stock/FormattedProse";
import { usePortfolioDigest } from "../../hooks/usePortfolioDigest";
import { usePortfolioDigestRegenerate } from "../../hooks/usePortfolioDigestRegenerate";
import { useQueueStatus } from "../../hooks/useQueue";
import { formatDate } from "../../lib/time";

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      {children}
    </section>
  );
}

export default function PortfolioDigestPanel() {
  const { data, isLoading, isError } = usePortfolioDigest();
  const { data: queue } = useQueueStatus();
  const regenerate = usePortfolioDigestRegenerate();

  const jobActive = [...(queue?.pending ?? []), ...(queue?.running ?? [])].some(
    (j) => j.job_type === "portfolio_digest",
  );
  const busy = jobActive || regenerate.isPending;

  if (isLoading) {
    return (
      <Shell>
        <p className="py-6 text-center text-sm text-zinc-600">loading portfolio summary…</p>
      </Shell>
    );
  }

  if (isError) {
    return (
      <Shell>
        <p className="py-6 text-center text-sm text-zinc-600">
          Portfolio summary is unavailable right now.
        </p>
      </Shell>
    );
  }

  const hasSummary = !!data?.as_of && !!data?.overview;

  return (
    <Shell>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Portfolio Summary
        </h2>
        <div className="flex items-center gap-2">
          {data?.stale && (
            <span className="text-xs text-amber-400">
              last successful summary shown — a regeneration attempt failed
            </span>
          )}
          {hasSummary && data?.as_of && (
            <span className="text-xs text-zinc-600">
              as of {formatDate(data.as_of.slice(0, 10)) || data.as_of}
            </span>
          )}
          <button
            onClick={() => regenerate.mutate()}
            disabled={busy}
            className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 transition-colors hover:border-zinc-500 disabled:opacity-40"
          >
            {busy ? "regenerating…" : "Regenerate"}
          </button>
        </div>
      </div>

      {!hasSummary ? (
        <p className="py-6 text-center text-sm text-zinc-600">
          No summary yet — click Regenerate to synthesize your tracked stocks' AI analyses.
        </p>
      ) : (
        <div className="space-y-4">
          <FormattedProse text={data!.overview} />

          {data!.capped && (
            <p className="text-xs text-zinc-600">
              Showing the {data!.stock_count} highest-conviction of {data!.total_tracked_count}{" "}
              tracked stocks — not all tracked stocks were included.
            </p>
          )}

          {data!.highlights.length > 0 && (
            <ul className="space-y-2">
              {data!.highlights.map((h) => (
                <li key={h.ticker} className="flex flex-wrap items-baseline gap-2 text-sm">
                  <Link
                    to={`/stocks/${h.ticker}`}
                    className="font-medium text-sky-400 hover:underline"
                  >
                    {h.ticker}
                  </Link>
                  <SignalBadge signal={h.signal as Signal} />
                  <ConvictionMeter conviction={h.conviction as Conviction} />
                  <span className="text-zinc-300">{h.note}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Shell>
  );
}

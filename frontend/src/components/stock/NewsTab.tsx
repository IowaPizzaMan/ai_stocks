// Spec: specs/021-stock-page-redesign US5 (FR-018, FR-021, FR-022, FR-022a)
// News is produced during a ticker pull, so this tab always reflects the last
// analysis and labels itself with that as-of date rather than implying live data.
// A month of a mega-cap runs to hundreds of articles, so the list reveals a
// page at a time while the timeline above always summarizes the whole window.
import { useState } from "react";
import type { NewsReport } from "../../api/types";
import { formatDate } from "../../lib/time";
import SentimentTimeline from "./SentimentTimeline";

const PAGE_SIZE = 25;

function ToneCounts({ bullish, bearish }: { bullish: number; bearish: number }) {
  if (!bullish && !bearish) {
    return <span className="text-[11px] text-zinc-600">neutral language</span>;
  }
  return (
    <span className="flex items-center gap-2 text-[11px]">
      {bullish > 0 && <span className="text-emerald-400">▲ {bullish} bullish</span>}
      {bearish > 0 && <span className="text-red-400">▼ {bearish} bearish</span>}
    </span>
  );
}

export default function NewsTab({ news }: { news?: NewsReport }) {
  const [visible, setVisible] = useState(PAGE_SIZE);

  if (!news || !news.articles.length) {
    return (
      <p className="py-12 text-center text-sm text-zinc-600">
        No recent news coverage found for this ticker — pull a fresh analysis to check again.
      </p>
    );
  }

  const shown = news.articles.slice(0, visible);
  const remaining = news.articles.length - shown.length;

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
            News tone over time
            {news.window_days ? (
              <span className="ml-2 font-normal normal-case tracking-normal text-zinc-600">
                last {news.window_days} days
              </span>
            ) : null}
          </h2>
          {news.as_of && (
            <span className="text-xs text-zinc-600">
              most recent article {formatDate(news.as_of) || news.as_of}
            </span>
          )}
        </div>
        <SentimentTimeline timeline={news.timeline} trend={news.trend} />
      </section>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Coverage ({news.news_count})
          </h2>
          <span className="text-xs text-zinc-600">
            showing {shown.length} of {news.news_count}
            {news.days_covered ? ` — ${news.days_covered} days with coverage` : ""}
          </span>
        </div>
        <ul className="space-y-4">
          {shown.map((a) => (
            <li key={a.url || `${a.headline}-${a.datetime}`} className="border-t border-zinc-800/60 pt-3 first:border-0 first:pt-0">
              <div className="mb-1 flex flex-wrap items-baseline gap-x-2 text-xs text-zinc-500">
                <span>{formatDate(a.date) || a.date}</span>
                <span>·</span>
                <span>{a.source}</span>
                <span className="ml-auto">
                  <ToneCounts bullish={a.bullish_count} bearish={a.bearish_count} />
                </span>
              </div>
              {a.url ? (
                <a
                  href={a.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm font-medium text-zinc-200 hover:text-sky-400"
                >
                  {a.headline}
                </a>
              ) : (
                <p className="text-sm font-medium text-zinc-200">{a.headline}</p>
              )}
              {a.ai_summary ? (
                <p className="mt-1 text-sm leading-relaxed text-zinc-400">{a.ai_summary}</p>
              ) : (
                a.text_excerpt && (
                  <p className="mt-1 text-xs leading-relaxed text-zinc-600">{a.text_excerpt}</p>
                )
              )}
            </li>
          ))}
        </ul>
        {remaining > 0 && (
          <button
            onClick={() => setVisible((v) => v + PAGE_SIZE)}
            className="mt-4 w-full rounded-lg border border-zinc-700 py-2 text-sm text-zinc-300 transition-colors hover:border-zinc-500 hover:text-white"
          >
            Show {Math.min(remaining, PAGE_SIZE)} more ({remaining} remaining)
          </button>
        )}
      </section>
    </div>
  );
}

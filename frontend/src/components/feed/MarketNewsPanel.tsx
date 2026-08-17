// Spec: specs/022-market-news-feed — market-wide headlines below the stock grid.
//
// A fixed list of the 20 most recent stories: no pagination, no "load more"
// (FR-003). Row treatment follows the stock page's News tab so the two news
// surfaces read as one system. No thumbnails in v1 (research D7) — 20 remote
// image fetches on the home page isn't worth the decoration.
import { Link } from "react-router-dom";
import { useMarketNews } from "../../hooks/useMarketNews";
import { formatDate } from "../../lib/time";

function Shell({ children, note }: { children: React.ReactNode; note?: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Market News
        </h2>
        {note}
      </div>
      {children}
    </section>
  );
}

function timeLabel(article: { datetime: string; date: string }): string {
  // "2026-08-16 20:30:00" — show the clock time, since these are same-day stories
  const clock = article.datetime.slice(11, 16);
  const day = formatDate(article.date) || article.date;
  return clock ? `${day} ${clock}` : day;
}

export default function MarketNewsPanel() {
  const { data, isLoading, isError } = useMarketNews();

  if (isLoading) {
    return (
      <Shell>
        <p className="py-6 text-center text-sm text-zinc-600">loading market news…</p>
      </Shell>
    );
  }

  // A news outage must never look like a page error — the grid above is fine.
  if (isError) {
    return (
      <Shell>
        <p className="py-6 text-center text-sm text-zinc-600">
          Market news is unavailable right now.
        </p>
      </Shell>
    );
  }

  const articles = data?.articles ?? [];
  if (!articles.length) {
    return (
      <Shell>
        <p className="py-6 text-center text-sm text-zinc-600">No recent market news found.</p>
      </Shell>
    );
  }

  const asOf = data?.as_of ? formatDate(data.as_of.slice(0, 10)) : null;

  return (
    <Shell
      note={
        <span className="text-xs text-zinc-600">
          {data?.stale
            ? "showing the last retrieved headlines — not current"
            : asOf
              ? `as of ${asOf}`
              : null}
        </span>
      }
    >
      <ul className="space-y-3">
        {articles.map((a) => (
          <li
            key={a.url}
            className="border-t border-zinc-800/60 pt-3 first:border-0 first:pt-0"
          >
            <div className="mb-0.5 flex flex-wrap items-baseline gap-x-2 text-xs text-zinc-500">
              <span>{timeLabel(a)}</span>
              <span>·</span>
              <span>{a.source}</span>
              {a.ticker && (
                <Link
                  to={`/stocks/${a.ticker}`}
                  className="rounded bg-zinc-800 px-1.5 py-0.5 font-medium text-sky-400 hover:bg-zinc-700"
                >
                  {a.ticker}
                </Link>
              )}
            </div>
            <a
              href={a.url}
              target="_blank"
              rel="noreferrer"
              className="text-sm text-zinc-200 hover:text-sky-400"
            >
              {a.headline}
            </a>
          </li>
        ))}
      </ul>
    </Shell>
  );
}

// The mixed general/stock/FMP-article news stream — specs/035-chat-and-news-upgrade
// US2 (FR-005, FR-006). Supersedes MarketNewsPanel on the News tab.
import { Link } from "react-router-dom";
import NewsBody from "../news/NewsBody";
import { useNews, useNewsRefresh } from "../../hooks/useNews";
import { useQueueStatus } from "../../hooks/useQueue";
import { formatDate } from "../../lib/time";
import type { NewsFeedArticle, NewsSourceType } from "../../api/types";

const TYPE_LABELS: Record<NewsSourceType, string> = {
  general: "Market",
  stock: "Company",
  fmp_article: "Analysis",
};

function Shell({ children, note }: { children: React.ReactNode; note?: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">News</h2>
        {note}
      </div>
      {children}
    </section>
  );
}

function timeLabel(article: NewsFeedArticle): string {
  if (!article.published_at) return article.published_date ?? "";
  const clock = article.published_at.slice(11, 16);
  const day = formatDate(article.published_date ?? article.published_at) || article.published_date;
  return clock ? `${day} ${clock}` : day || "";
}

function NewsRow({ article }: { article: NewsFeedArticle }) {
  return (
    <li className="border-t border-zinc-800/60 pt-3 first:border-0 first:pt-0">
      <div className="mb-0.5 flex flex-wrap items-baseline gap-x-2 text-xs text-zinc-500">
        <span>{timeLabel(article)}</span>
        <span>·</span>
        <span>{article.publisher ?? "unknown"}</span>
        <span className="rounded bg-zinc-800 px-1.5 py-0.5 font-medium text-zinc-400">
          {TYPE_LABELS[article.source_type]}
        </span>
        {/* Singular /stock/:TICKER — MarketNewsPanel's chip pointed at the
            plural /stocks/:TICKER, a dead link (research.md R5, KNOWN_ISSUES.md). */}
        {article.tickers.map((ticker) => (
          <Link
            key={ticker}
            to={`/stock/${ticker}`}
            className="rounded bg-zinc-800 px-1.5 py-0.5 font-medium text-sky-400 hover:bg-zinc-700"
          >
            {ticker}
          </Link>
        ))}
      </div>
      <a
        href={article.url}
        target="_blank"
        rel="noreferrer"
        className="text-sm text-zinc-200 hover:text-sky-400"
      >
        {article.title}
      </a>
      <NewsBody bodyHtml={article.body_html} bodyText={article.body_text} />
    </li>
  );
}

export default function NewsFeed() {
  const { data, isLoading, isError } = useNews();
  const { data: queue } = useQueueStatus();
  const refresh = useNewsRefresh();

  const jobActive = [...(queue?.pending ?? []), ...(queue?.running ?? [])].some(
    (j) => j.job_type === "market_news_pull",
  );
  const busy = jobActive || refresh.isPending;

  if (isLoading) {
    return (
      <Shell>
        <p className="py-6 text-center text-sm text-zinc-600">loading news…</p>
      </Shell>
    );
  }

  if (isError) {
    return (
      <Shell>
        <p className="py-6 text-center text-sm text-zinc-600">News is unavailable right now.</p>
      </Shell>
    );
  }

  const articles = data?.articles ?? [];

  return (
    <Shell
      note={
        <div className="flex items-center gap-2">
          {data?.as_of && <span className="text-xs text-zinc-600">as of {formatDate(data.as_of)}</span>}
          <button
            onClick={() => refresh.mutate()}
            disabled={busy}
            className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 transition-colors hover:border-zinc-500 disabled:opacity-40"
          >
            {busy ? "refreshing…" : "Refresh"}
          </button>
        </div>
      }
    >
      {articles.length === 0 ? (
        <p className="py-6 text-center text-sm text-zinc-600">No recent news found.</p>
      ) : (
        <ul className="space-y-3">
          {articles.map((article) => (
            <NewsRow key={article.url} article={article} />
          ))}
        </ul>
      )}
    </Shell>
  );
}

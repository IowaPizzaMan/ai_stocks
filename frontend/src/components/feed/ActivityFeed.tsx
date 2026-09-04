// specs/037-stocks-conviction-and-activity US3 (FR-015-FR-022).
// Recently added/updated stocks — last 100 events, newest first, paged.
import { useState } from "react";
import { Link } from "react-router-dom";
import type { StockEvent } from "../../api/types";
import { useActivityFeed } from "../../hooks/useStockEvents";
import { formatMonthDay } from "../../lib/time";

const PAGE_SIZE = 20;

function transitionText(event: StockEvent): string | null {
  if (!event.changes) return null;
  const parts: string[] = [];
  if (event.changes.signal) parts.push(`signal ${event.changes.signal.from}→${event.changes.signal.to}`);
  if (event.changes.conviction) {
    parts.push(`conviction ${event.changes.conviction.from}→${event.changes.conviction.to}`);
  }
  return parts.join(", ") || null;
}

function EventRow({ event }: { event: StockEvent }) {
  const verb = event.event_type === "added" ? "added" : "updated";
  const date = formatMonthDay(event.occurred_at);
  const transition = transitionText(event);

  return (
    <li
      className={`flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm ${
        event.changed ? "bg-sky-500/10" : ""
      }`}
    >
      <span className="min-w-0 truncate text-zinc-300">
        <Link to={`/stock/${event.ticker}`} className="font-medium text-zinc-100 hover:text-sky-400">
          {event.ticker}
        </Link>{" "}
        was {verb} on {date}
        {transition && <span className="text-sky-400"> — {transition}</span>}
        {event.reason && <span className="text-zinc-500"> ({event.reason})</span>}
      </span>
      {event.changed && (
        <span className="shrink-0 rounded-full bg-sky-500/20 px-2 py-0.5 text-xs text-sky-400">
          changed
        </span>
      )}
    </li>
  );
}

export default function ActivityFeed() {
  const [page, setPage] = useState(1);
  const { data, isLoading, isError } = useActivityFeed(page, PAGE_SIZE);

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const hasNext = page * PAGE_SIZE < total;
  const hasPrev = page > 1;

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-zinc-500">
        Recent Activity
      </h2>

      {isLoading && <p className="py-4 text-center text-sm text-zinc-600">Loading…</p>}
      {isError && (
        <p className="py-4 text-center text-sm text-red-400">Couldn't load recent activity.</p>
      )}
      {!isLoading && !isError && items.length === 0 && (
        <p className="py-4 text-center text-sm text-zinc-600">No activity yet.</p>
      )}

      {!isLoading && !isError && items.length > 0 && (
        <>
          <ul className="space-y-1">
            {items.map((event, i) => (
              <EventRow key={`${event.ticker}-${event.occurred_at}-${i}`} event={event} />
            ))}
          </ul>

          {(hasPrev || hasNext) && (
            <div className="mt-3 flex items-center justify-between text-sm">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={!hasPrev}
                className="rounded-lg border border-zinc-700 px-3 py-1 text-zinc-300 transition-colors hover:border-zinc-500 disabled:opacity-40"
              >
                ← Newer
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={!hasNext}
                className="rounded-lg border border-zinc-700 px-3 py-1 text-zinc-300 transition-colors hover:border-zinc-500 disabled:opacity-40"
              >
                Older →
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}

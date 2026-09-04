// specs/037-stocks-conviction-and-activity US5 (FR-027-FR-030).
// A per-stock trail of "added" + every real signal/conviction change, each
// with a rule-derived reason — a filtered view of the same stock_events log
// the Stocks-page activity feed reads (GET /events/{ticker}).
import { useChangeHistory } from "../../hooks/useStockEvents";
import { formatDate } from "../../lib/time";

function transitionText(event: { changes: { signal?: { from: string; to: string }; conviction?: { from: string; to: string } } | null }): string {
  if (!event.changes) return "added";
  const parts: string[] = [];
  if (event.changes.signal) parts.push(`signal ${event.changes.signal.from}→${event.changes.signal.to}`);
  if (event.changes.conviction) {
    parts.push(`conviction ${event.changes.conviction.from}→${event.changes.conviction.to}`);
  }
  return parts.join(", ");
}

export default function ChangeHistory({ ticker }: { ticker: string }) {
  const { data, isLoading, isError } = useChangeHistory(ticker);
  const items = data?.items ?? [];

  if (isLoading) return <p className="text-sm text-zinc-600">Loading…</p>;
  if (isError) return <p className="text-sm text-red-400">Couldn't load change history.</p>;

  if (items.length <= 1) {
    return (
      <p className="text-sm text-zinc-500">
        {items.length === 1
          ? `Added ${formatDate(items[0].occurred_at) || items[0].occurred_at} — no changes recorded yet.`
          : "No history yet."}
      </p>
    );
  }

  return (
    <ul className="space-y-2 text-sm">
      {items.map((event, i) => (
        <li key={`${event.event_type}-${event.occurred_at}-${i}`} className="flex gap-2">
          <span className="shrink-0 text-xs text-zinc-600">
            {formatDate(event.occurred_at) || event.occurred_at}
          </span>
          <span className="text-zinc-300">
            {event.event_type === "added" ? "Added" : transitionText(event)}
            {event.reason && <span className="text-zinc-500"> — {event.reason}</span>}
          </span>
        </li>
      ))}
    </ul>
  );
}

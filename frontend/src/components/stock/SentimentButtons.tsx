// specs/028-dashboard-tweaks-batch US3 (FR-005, FR-006, FR-006a) — thumbs
// up/down next to the ticker on the stock detail page. Rendered only when
// the ticker is tracked (a tag can only ever exist for a tracked stock —
// contracts/stock-sentiment-api.md, R11); the caller passes `tracked` from
// the same ticker-record fetch that already answers that question.
//
// Active state is conveyed by fill + outline, not color alone, and by
// aria-pressed so it's operable and assertable without relying on icon
// rendering.
import type { Sentiment } from "../../api/types";
import { useClearSentiment, useSetSentiment } from "../../hooks/useSentiment";

function ThumbsUpIcon({ filled }: { filled: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
      aria-hidden="true"
    >
      <path d="M7 10v11H4a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1h3Zm0 0 5-7 1.5 1a3 3 0 0 1 .8 3l-.8 2.5H18a2 2 0 0 1 2 2.3l-1.3 7A2 2 0 0 1 16.7 21H7" />
    </svg>
  );
}

function ThumbsDownIcon({ filled }: { filled: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
      aria-hidden="true"
    >
      <path d="M17 14V3h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-3Zm0 0-5 7-1.5-1a3 3 0 0 1-.8-3l.8-2.5H6a2 2 0 0 1-2-2.3l1.3-7A2 2 0 0 1 7.3 3H17" />
    </svg>
  );
}

export default function SentimentButtons({
  ticker,
  tracked,
  sentiment,
}: {
  ticker: string;
  /** Whether this ticker exists in the tracked universe (ticker_index). */
  tracked: boolean;
  sentiment: Sentiment | null | undefined;
}) {
  const setSentiment = useSetSentiment();
  const clearSentiment = useClearSentiment();

  if (!tracked) return null;

  const liked = sentiment === "liked";
  const disliked = sentiment === "disliked";

  const toggle = (value: Sentiment) => {
    // Toggle-off is a server decision (PUT with the currently-active value
    // clears it) — the button never needs to branch to DELETE for that case.
    setSentiment.mutate({ ticker, sentiment: value });
  };

  return (
    <span className="flex items-center gap-1">
      <button
        type="button"
        aria-label={`Like ${ticker}`}
        aria-pressed={liked}
        onClick={() => toggle("liked")}
        disabled={setSentiment.isPending || clearSentiment.isPending}
        className={`rounded-full border p-1.5 transition-colors disabled:opacity-40 ${
          liked
            ? "border-emerald-500 bg-emerald-500/10 text-emerald-400"
            : "border-zinc-700 text-zinc-500 hover:border-zinc-500 hover:text-zinc-300"
        }`}
      >
        <ThumbsUpIcon filled={liked} />
      </button>
      <button
        type="button"
        aria-label={`Dislike ${ticker}`}
        aria-pressed={disliked}
        onClick={() => toggle("disliked")}
        disabled={setSentiment.isPending || clearSentiment.isPending}
        className={`rounded-full border p-1.5 transition-colors disabled:opacity-40 ${
          disliked
            ? "border-red-500 bg-red-500/10 text-red-400"
            : "border-zinc-700 text-zinc-500 hover:border-zinc-500 hover:text-zinc-300"
        }`}
      >
        <ThumbsDownIcon filled={disliked} />
      </button>
    </span>
  );
}

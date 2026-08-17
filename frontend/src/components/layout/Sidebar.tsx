// Spec: specs/component-specs/frontend/components/layout/Sidebar.md
import { useState } from "react";
import { NavLink } from "react-router-dom";
import type { WatchlistItem } from "../../api/types";
import { useRemoveFromWatchlist, useWatchlist } from "../../hooks/useWatchlist";
import RemoveIcon from "../shared/RemoveIcon";

const DOT: Record<string, string> = {
  bullish: "bg-emerald-400",
  bearish: "bg-red-400",
  neutral: "bg-zinc-400",
};

function WatchlistRow({ item }: { item: WatchlistItem }) {
  const removeMutation = useRemoveFromWatchlist();
  // Driven by JS, not a CSS :hover/:focus-within pseudo-class, so hover and
  // keyboard focus reveal the control identically (and so it's testable
  // without a real browser layout engine).
  const [revealed, setRevealed] = useState(false);

  return (
    <li
      className="relative"
      onMouseEnter={() => setRevealed(true)}
      onMouseLeave={() => setRevealed(false)}
      onFocus={() => setRevealed(true)}
      onBlur={() => setRevealed(false)}
    >
      <NavLink
        to={`/stock/${item.ticker}`}
        className={({ isActive }) =>
          `flex items-center justify-between rounded-md px-2 py-1.5 transition-colors ${
            isActive ? "bg-zinc-800 text-white" : "hover:bg-zinc-900 hover:text-zinc-200"
          }`
        }
      >
        <span className="font-medium">{item.ticker}</span>
        <span className="flex items-center gap-1.5">
          {item.status === "removed_from_market" && (
            <span title="removed from market" className="text-amber-400">
              ⚠
            </span>
          )}
          {item.last_signal && (
            <span
              className={`h-1.5 w-1.5 rounded-full ${DOT[item.last_signal] ?? DOT.neutral}`}
            />
          )}
        </span>
      </NavLink>
      {/* Sibling of the NavLink, not nested inside it — a click here can
          never bubble into the link's navigation. */}
      <button
        type="button"
        aria-label={`Remove ${item.ticker} from watchlist`}
        disabled={removeMutation.isPending}
        onClick={() => removeMutation.mutate(item.ticker)}
        className={`absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-0.5 text-zinc-500 transition-opacity hover:bg-zinc-800 hover:text-red-400 disabled:cursor-not-allowed disabled:opacity-50 ${
          revealed ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      >
        <RemoveIcon className="h-3 w-3" />
      </button>
      {removeMutation.isError && (
        <p role="alert" className="px-2 pb-1 text-[10px] text-red-400">
          Couldn't remove {item.ticker} — try again.
        </p>
      )}
    </li>
  );
}

export default function Sidebar() {
  const { data, isLoading } = useWatchlist();

  return (
    <aside className="w-56 shrink-0 border-r border-zinc-800 p-4 text-sm text-zinc-400">
      <p className="mb-3 font-medium text-zinc-300">Watchlist</p>
      {isLoading && <p className="text-xs text-zinc-600">loading…</p>}
      {!isLoading && (data?.items.length ?? 0) === 0 && (
        <p className="text-xs text-zinc-600">
          Empty — add tickers from the feed or a stock page.
        </p>
      )}
      <ul className="space-y-1">
        {data?.items.map((item) => (
          <WatchlistRow key={item.ticker} item={item} />
        ))}
      </ul>
    </aside>
  );
}

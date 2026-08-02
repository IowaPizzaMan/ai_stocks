// Spec: specs/component-specs/frontend/components/layout/Sidebar.md
import { NavLink } from "react-router-dom";
import { useWatchlist } from "../../hooks/useWatchlist";

const DOT: Record<string, string> = {
  bullish: "bg-emerald-400",
  bearish: "bg-red-400",
  neutral: "bg-zinc-400",
};

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
          <li key={item.ticker}>
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
          </li>
        ))}
      </ul>
    </aside>
  );
}

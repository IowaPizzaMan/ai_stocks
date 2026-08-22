// specs/028-dashboard-tweaks-batch US4 (FR-015, FR-016, FR-016a, FR-016b).
import { Link } from "react-router-dom";
import type { CongressSummaryResponse } from "../../api/types";

export default function CongressSummary({ data }: { data: CongressSummaryResponse }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
          Most bought — last {data.window_days} days
        </h3>
        {data.most_bought.length === 0 ? (
          <p className="text-sm text-zinc-600">No notable buying activity in this window.</p>
        ) : (
          <ul className="space-y-1">
            {data.most_bought.map((m) => (
              <li key={m.ticker} className="flex items-center justify-between text-sm">
                <Link to={`/stock/${m.ticker}`} className="font-medium text-sky-400 hover:underline">
                  {m.ticker}
                </Link>
                <span className="tabular-nums text-zinc-400">{m.buy_count} buys</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
          High-dollar trades (≥ {data.high_dollar_threshold})
        </h3>
        {data.high_dollar.length === 0 ? (
          <p className="text-sm text-zinc-600">No high-dollar trades in this window.</p>
        ) : (
          <ul className="space-y-1">
            {data.high_dollar.map((t) => (
              <li key={t.trade_id} className="flex items-center justify-between gap-2 text-sm">
                {t.ticker ? (
                  <Link to={`/stock/${t.ticker}`} className="font-medium text-sky-400 hover:underline">
                    {t.ticker}
                  </Link>
                ) : (
                  <span className="text-zinc-500">{t.asset_description ?? "—"}</span>
                )}
                <span className="tabular-nums text-zinc-400">{t.amount_range}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

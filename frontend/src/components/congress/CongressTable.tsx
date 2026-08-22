// specs/028-dashboard-tweaks-batch US4 (FR-012, FR-017, FR-018).
// Both dates are shown deliberately — disclosures routinely lag their trade
// by months (the confirmed sample data showed a 16-month gap), so collapsing
// to one date would actively mislead.
import { Link } from "react-router-dom";
import type { CongressTrade } from "../../api/types";

export default function CongressTable({ trades }: { trades: CongressTrade[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wide text-zinc-500">
            <th className="pb-2 pr-3">Chamber</th>
            <th className="pb-2 pr-3">Politician</th>
            <th className="pb-2 pr-3">Ticker</th>
            <th className="pb-2 pr-3">Asset</th>
            <th className="pb-2 pr-3">Type</th>
            <th className="pb-2 pr-3">Amount</th>
            <th className="pb-2 pr-3">Traded</th>
            <th className="pb-2">Disclosed</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => (
            <tr key={t.trade_id} className="border-t border-zinc-800">
              <td className="py-1.5 pr-3 capitalize text-zinc-400">{t.chamber}</td>
              <td className="py-1.5 pr-3 text-zinc-300">{t.politician}</td>
              <td className="py-1.5 pr-3">
                {t.ticker ? (
                  <Link to={`/stock/${t.ticker}`} className="font-medium text-sky-400 hover:underline">
                    {t.ticker}
                  </Link>
                ) : (
                  <span className="text-zinc-500">—</span>
                )}
              </td>
              <td className="py-1.5 pr-3 max-w-[16rem] truncate text-zinc-400">
                {t.asset_description ?? "—"}
              </td>
              <td
                className={`py-1.5 pr-3 ${
                  t.transaction_type?.toLowerCase() === "purchase" ? "text-emerald-400" : "text-red-400"
                }`}
              >
                {t.transaction_type}
              </td>
              <td className="py-1.5 pr-3 tabular-nums text-zinc-300">{t.amount_range ?? "—"}</td>
              <td className="py-1.5 pr-3 tabular-nums text-zinc-500">{t.transaction_date}</td>
              <td className="py-1.5 tabular-nums text-zinc-500">{t.disclosure_date}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

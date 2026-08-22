// Spec: specs/029-company-profile-tweaks/contracts/company-profile-api.md (US6)
import { Link } from "react-router-dom";
import { usePeers } from "../../hooks/useCompanyProfile";
import { formatCompact } from "../earnings/EarningsTable";

export default function PeersSection({ ticker }: { ticker: string }) {
  const { data, isLoading } = usePeers(ticker);
  const peers = data?.peers ?? [];

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">Peers</h2>

      {isLoading && <p className="text-sm text-zinc-600">loading peers…</p>}

      {!isLoading && peers.length === 0 && (
        <p className="text-sm text-zinc-500">No peers published for this company.</p>
      )}

      {!isLoading && peers.length > 0 && (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="text-[11px] uppercase tracking-wide text-zinc-500">
              <th className="pb-2 font-normal">Symbol</th>
              <th className="pb-2 font-normal">Company</th>
              <th className="pb-2 text-right font-normal">Price</th>
              <th className="pb-2 text-right font-normal">Mkt Cap</th>
            </tr>
          </thead>
          <tbody>
            {peers.map((p) => (
              <tr key={p.symbol} className="border-t border-zinc-800/60">
                <td className="py-1.5">
                  <Link to={`/stock/${p.symbol}`} className="font-medium text-sky-400 hover:text-sky-300">
                    {p.symbol}
                  </Link>
                </td>
                <td className="py-1.5 text-zinc-300">{p.name ?? "—"}</td>
                <td className="py-1.5 text-right text-zinc-300">
                  {p.price != null ? `$${p.price.toFixed(2)}` : "—"}
                </td>
                <td className="py-1.5 text-right text-zinc-300">{formatCompact(p.market_cap)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

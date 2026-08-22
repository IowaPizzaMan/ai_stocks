// Spec: specs/component-specs/frontend/pages/Sectors.md
// /sectors — all-sectors summary chart + sector cards.
// /sectors/:sector — signal heatmap + sorted list for one sector.
import { useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import type { AnalysisFeedItem, SectorSummary } from "../api/types";
import ConvictionMeter from "../components/shared/ConvictionMeter";
import SectorEtfChart from "../components/sectors/SectorEtfChart";
import SignalBadge from "../components/shared/SignalBadge";
import { useSectorAnalysis, useSectors } from "../hooks/useSectors";
import { relativeTime } from "../lib/time";

// Signal palette — matches SignalBadge/heatmap semantics (status colors, always
// paired with the legend label, never color alone).
const SIGNAL_COLORS = {
  bullish: "#10b981", // emerald-500
  neutral: "#52525b", // zinc-600
  bearish: "#ef4444", // red-500
};

// 029-company-profile-tweaks (FR-027) — matches the backend's reserved
// bucket name (backend/routers/sectors.py::UNCLASSIFIED) for tracked stocks
// whose profile hasn't been fetched yet (or published no sector).
const UNCLASSIFIED = "Unclassified";

const SIGNAL_RANK = { bullish: 2, neutral: 1, bearish: 0 } as const;
const CONVICTION_RANK = { high: 2, medium: 1, low: 0 } as const;
// hex-alpha suffix for tile fills — higher conviction, stronger wash
const CONVICTION_ALPHA = { high: "38", medium: "24", low: "12" } as const;

export default function Sectors() {
  const { sector } = useParams();

  useEffect(() => {
    document.title = sector ? `StockAI — ${sector}` : "StockAI — Sectors";
  }, [sector]);

  return sector ? <SectorDetail sector={sector} /> : <SectorOverview />;
}

// --- Overview ----------------------------------------------------------------

function SectorOverview() {
  const { data: sectors, isLoading, isError } = useSectors();

  // The ETF momentum chart (specs/028-dashboard-tweaks-batch US5) has its own
  // independent data source and loading/empty/error handling, so it renders
  // once here regardless of which state the analysis-based rollup below is in.
  let body: React.ReactNode;
  if (isLoading) {
    body = <p className="py-12 text-center text-sm text-zinc-500">loading sectors…</p>;
  } else if (isError) {
    body = (
      <p className="py-12 text-center text-sm text-red-400">
        Couldn't reach the API — is the backend running?
      </p>
    );
  } else if (!sectors || sectors.length === 0) {
    body = (
      <div className="py-16 text-center text-zinc-500">
        <p className="mb-1 text-lg text-zinc-400">No sector data yet</p>
        <p className="text-sm">Sectors populate as analyses complete — pull some tickers from the feed first.</p>
      </div>
    );
  } else {
    // Unclassified sorts last regardless of its bullish ratio — it's "awaiting
    // a pull", not a sector to rank among real ones (FR-027).
    const sorted = [...sectors].sort((a, b) => {
      const aUnclassified = a.sector === UNCLASSIFIED;
      const bUnclassified = b.sector === UNCLASSIFIED;
      if (aUnclassified !== bUnclassified) return aUnclassified ? 1 : -1;
      return b.bullish_count / b.ticker_count - a.bullish_count / a.ticker_count;
    });
    body = (
      <>
        <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Signal mix by sector
          </h2>
          <p className="mb-4 text-xs text-zinc-500">
            Share of tickers bullish / neutral / bearish, strongest sector first.
          </p>
          <div className="space-y-2">
            {sorted.map((s) => (
              <SectorRow key={s.sector} summary={s} />
            ))}
          </div>
          <div className="mt-3 flex gap-4">
            {(["bullish", "neutral", "bearish"] as const).map((sig) => (
              <span key={sig} className="flex items-center gap-1.5 text-[11px] capitalize text-zinc-400">
                <span className="inline-block h-2 w-2 rounded-sm" style={{ backgroundColor: SIGNAL_COLORS[sig] }} />
                {sig}
              </span>
            ))}
          </div>
        </section>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sorted.map((s) => (
            <SectorCard key={s.sector} summary={s} />
          ))}
        </div>
      </>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-white">Sectors</h1>
      <SectorEtfChart />
      {body}
    </div>
  );
}

function SectorRow({ summary }: { summary: SectorSummary }) {
  const total = summary.ticker_count || 1;
  const segments = (["bullish", "neutral", "bearish"] as const)
    .map((sig) => ({ sig, count: summary[`${sig}_count`] }))
    .filter((seg) => seg.count > 0);
  const isUnclassified = summary.sector === UNCLASSIFIED;

  return (
    <Link
      to={`/sectors/${encodeURIComponent(summary.sector)}`}
      data-sector-row={summary.sector}
      className="group grid grid-cols-[10rem_1fr_2.5rem] items-center gap-3"
      title={
        isUnclassified
          ? "Tracked stocks awaiting their next analysis pull, which fetches their sector"
          : `${summary.sector}: ${summary.bullish_count} bullish · ${summary.neutral_count} neutral · ${summary.bearish_count} bearish`
      }
    >
      <span
        className={`truncate text-sm group-hover:text-white ${isUnclassified ? "italic text-zinc-500" : "text-zinc-300"}`}
      >
        {summary.sector}
      </span>
      <span className="flex h-4 overflow-hidden rounded">
        {segments.map((seg) => (
          <span
            key={seg.sig}
            className="h-full transition-opacity group-hover:opacity-80"
            style={{
              width: `${(seg.count / total) * 100}%`,
              backgroundColor: SIGNAL_COLORS[seg.sig],
              marginRight: seg === segments[segments.length - 1] ? 0 : 2,
            }}
          />
        ))}
      </span>
      <span className="text-right text-xs tabular-nums text-zinc-500">{summary.ticker_count}</span>
    </Link>
  );
}

function SectorCard({ summary }: { summary: SectorSummary }) {
  const isUnclassified = summary.sector === UNCLASSIFIED;
  return (
    <div
      data-sector-card={summary.sector}
      className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 transition-colors hover:border-zinc-700"
    >
      <Link to={`/sectors/${encodeURIComponent(summary.sector)}`} className="block">
        <div className="mb-2 flex items-baseline justify-between">
          <span className={`font-medium ${isUnclassified ? "italic text-zinc-500" : "text-white"}`}>
            {summary.sector}
          </span>
          <span className="text-xs text-zinc-500">{summary.ticker_count} tickers</span>
        </div>
        {isUnclassified ? (
          <p className="text-xs text-zinc-500">Awaiting their next analysis pull to fetch a sector.</p>
        ) : (
          <p className="text-xs text-zinc-400">
            <span className="text-emerald-400">{summary.bullish_count} bullish</span>
            {" · "}
            <span className="text-zinc-400">{summary.neutral_count} neutral</span>
            {" · "}
            <span className="text-red-400">{summary.bearish_count} bearish</span>
          </p>
        )}
        {summary.top_ticker && (
          <p className="mt-2 text-xs text-zinc-500">
            top: <span className="font-mono text-zinc-300">{summary.top_ticker}</span>
          </p>
        )}
      </Link>
      <Link
        to={`/?sector=${encodeURIComponent(summary.sector)}`}
        className="mt-3 inline-block text-xs text-sky-400 hover:text-sky-300"
      >
        View in Feed →
      </Link>
    </div>
  );
}

// --- Detail ------------------------------------------------------------------

function SectorDetail({ sector }: { sector: string }) {
  const { data: items, isLoading, isError } = useSectorAnalysis(sector);
  const navigate = useNavigate();

  if (isLoading) return <p className="py-12 text-center text-sm text-zinc-500">loading {sector}…</p>;
  if (isError)
    return <p className="py-12 text-center text-sm text-red-400">Couldn't reach the API — is the backend running?</p>;

  const sorted = [...(items ?? [])].sort(
    (a, b) =>
      SIGNAL_RANK[b.signal] - SIGNAL_RANK[a.signal] ||
      CONVICTION_RANK[b.conviction] - CONVICTION_RANK[a.conviction],
  );

  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between">
        <div className="flex items-baseline gap-3">
          <Link to="/sectors" className="text-sm text-zinc-500 hover:text-zinc-300">
            ← Sectors
          </Link>
          <h1 className="text-xl font-semibold text-white">{sector}</h1>
        </div>
        <Link to={`/?sector=${encodeURIComponent(sector)}`} className="text-xs text-sky-400 hover:text-sky-300">
          View in Feed →
        </Link>
      </div>

      {sorted.length === 0 ? (
        <p className="py-12 text-center text-sm text-zinc-500">no analyzed tickers in this sector yet</p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-5 lg:grid-cols-8">
            {sorted.map((item) => (
              <SignalTile key={item.ticker} item={item} onClick={() => navigate(`/stock/${item.ticker}`)} />
            ))}
          </div>

          <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-zinc-500">
                <tr>
                  <th className="pb-2 pr-4">Ticker</th>
                  <th className="pb-2 pr-4">Signal</th>
                  <th className="pb-2 pr-4">Conviction</th>
                  <th className="pb-2 pr-4">Analyzed</th>
                  <th className="pb-2">Summary</th>
                </tr>
              </thead>
              <tbody className="text-zinc-300">
                {sorted.map((item) => (
                  <tr
                    key={item.ticker}
                    className="cursor-pointer border-t border-zinc-800/60 hover:bg-zinc-800/40"
                    onClick={() => navigate(`/stock/${item.ticker}`)}
                  >
                    <td className="py-2 pr-4 font-mono font-medium text-white">{item.ticker}</td>
                    <td className="py-2 pr-4">
                      <SignalBadge signal={item.signal} />
                    </td>
                    <td className="py-2 pr-4">
                      <ConvictionMeter conviction={item.conviction} />
                    </td>
                    <td className="py-2 pr-4 whitespace-nowrap text-xs text-zinc-500">
                      {relativeTime(item.timestamp)}
                    </td>
                    <td className="max-w-md truncate py-2 text-xs text-zinc-400">{item.summary}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}

function SignalTile({ item, onClick }: { item: AnalysisFeedItem; onClick: () => void }) {
  const base = SIGNAL_COLORS[item.signal];
  const alpha = item.signal === "neutral" ? "35" : CONVICTION_ALPHA[item.conviction];
  return (
    <button
      onClick={onClick}
      className="rounded-lg border p-3 text-left transition-transform hover:scale-[1.03]"
      style={{ backgroundColor: `${base}${alpha}`, borderColor: `${base}55` }}
      title={`${item.ticker} — ${item.signal}, ${item.conviction} conviction`}
    >
      <span className="block text-sm font-bold text-white">{item.ticker}</span>
      <ConvictionMeter conviction={item.conviction} />
    </button>
  );
}

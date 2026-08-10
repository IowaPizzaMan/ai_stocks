// Spec: specs/component-specs/frontend/pages/StockDetail.md
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import type { Analysis } from "../api/types";
import ConvictionMeter from "../components/shared/ConvictionMeter";
import SignalBadge from "../components/shared/SignalBadge";
import BreadthDivergenceChart from "../components/stock/BreadthDivergenceChart";
import PriceChart from "../components/stock/PriceChart";
import TFCChartGrid from "../components/stock/TFCChartGrid";
import {
  FundamentalsTab,
  InsiderTab,
  InstitutionalTab,
  SentimentTab,
  TechnicalsTab,
} from "../components/stock/tabs";
import { useTickerAnalysis, useTickerRecord } from "../hooks/useAnalysis";
import { useMarketBreadth } from "../hooks/useMarketBreadth";
import { useStockPriceHistory } from "../hooks/usePriceHistory";
import { useEnqueueTicker, useQueueStatus } from "../hooks/useQueue";
import { useAddToWatchlist } from "../hooks/useWatchlist";
import type { Timeframe } from "../lib/strat/displayWindow";
import { formatDate, relativeTime } from "../lib/time";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "technicals", label: "Technicals" },
  { id: "fundamentals", label: "Fundamentals" },
  { id: "insider", label: "Insider" },
  { id: "institutional", label: "Institutional" },
  { id: "sentiment", label: "Sentiment" },
  { id: "ai-summary", label: "AI Summary" },
];

export default function StockDetail() {
  const { ticker = "" } = useParams<{ ticker: string }>();
  const symbol = ticker.toUpperCase();
  const location = useLocation();
  const navigate = useNavigate();
  const activeTab = location.hash.replace("#", "") || "overview";

  const [deepDiveTf, setDeepDiveTf] = useState<Timeframe>("1Y");
  const { data: analyses, isLoading } = useTickerAnalysis(symbol);
  const { data: record } = useTickerRecord(symbol);
  const { data: queue } = useQueueStatus();
  const { data: priceData } = useStockPriceHistory(symbol, ["1D", "1W", "1M", "1Y", "5Y", "MAX"]);
  const enqueue = useEnqueueTicker();
  const addToWatchlist = useAddToWatchlist();

  useEffect(() => {
    document.title = `StockAI — ${symbol}`;
  }, [symbol]);

  const latest = analyses?.[0];
  const queuedJob = [...(queue?.pending ?? []), ...(queue?.running ?? [])].find(
    (j) => j.ticker === symbol,
  );
  const removed = record?.status === "removed_from_market";

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-4">
          <Link to="/" className="text-zinc-500 hover:text-zinc-300">
            ←
          </Link>
          <h1 className="text-3xl font-bold text-white">{symbol}</h1>
          {record?.name && <span className="text-zinc-400">{record.name}</span>}
          {latest && (
            <>
              <SignalBadge signal={latest.signal} />
              <ConvictionMeter conviction={latest.conviction} />
            </>
          )}
          {removed && (
            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-xs text-amber-400">
              removed from market
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {queuedJob ? (
            <span className="flex items-center gap-2 rounded-lg bg-sky-500/10 px-3 py-1.5 text-sm text-sky-400">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-sky-400" />
              {queuedJob.status === "running" ? "analyzing…" : "queued"}
            </span>
          ) : (
            <button
              onClick={() => enqueue.mutate(symbol)}
              disabled={enqueue.isPending}
              title={
                removed
                  ? "Flagged as removed from market — pulling re-checks and reactivates it if it now resolves"
                  : undefined
              }
              className={`rounded-lg bg-sky-600 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-sky-500 disabled:opacity-40 ${removed ? "opacity-70" : ""}`}
            >
              Pull ▶
            </button>
          )}
          <button
            onClick={() => addToWatchlist.mutate(symbol)}
            className="rounded-lg border border-zinc-700 px-4 py-1.5 text-sm text-zinc-300 transition-colors hover:border-zinc-500"
          >
            + Watchlist
          </button>
        </div>
      </div>

      {isLoading && <p className="py-12 text-center text-zinc-500">loading…</p>}

      {!isLoading && !latest && (
        <div className="py-16 text-center text-zinc-500">
          <p className="mb-2 text-lg text-zinc-400">No analysis yet for {symbol}</p>
          {queuedJob ? (
            <p className="text-sm">
              Analysis {queuedJob.status === "running" ? "running now" : "queued"} — this
              page updates when it lands.
            </p>
          ) : (
            <button
              onClick={() => enqueue.mutate(symbol)}
              className="mt-2 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500"
            >
              Pull Analysis ▶
            </button>
          )}
        </div>
      )}

      {/* TFC grid + deep-dive chart render for any ticker with price data */}
      <div className="mb-6">
        <TFCChartGrid
          priceData={priceData}
          tfcStatus={latest?.sub_reports?.technical?.strat_result?.tfc?.status}
        />
      </div>
      <div className="mb-6 rounded-xl border border-zinc-800 bg-zinc-900 p-4">
        <p className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Deep dive — {deepDiveTf}
        </p>
        <PriceChart
          priceData={priceData[deepDiveTf] ?? []}
          defaultTimeframe="1Y"
          onTimeframeChange={setDeepDiveTf}
        />
      </div>

      {latest && (
        <>
          <nav className="flex flex-wrap gap-1 border-b border-zinc-800">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => navigate(`#${tab.id}`, { replace: true })}
                className={`px-3 py-2 text-sm transition-colors ${
                  activeTab === tab.id
                    ? "border-b-2 border-sky-500 text-white"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                {tab.label}
              </button>
            ))}
            <span className="ml-auto self-center text-xs text-zinc-600">
              analyzed {relativeTime(latest.timestamp)}
              {formatDate(latest.timestamp) && ` — data as of ${formatDate(latest.timestamp)}`}
            </span>
          </nav>

          <div className="mt-6">
            {activeTab === "overview" && <OverviewTab analysis={latest} />}
            {activeTab === "technicals" && <TechnicalsTab technical={latest.sub_reports?.technical} />}
            {activeTab === "fundamentals" && <FundamentalsTab fundamental={latest.sub_reports?.fundamental} ticker={ticker} />}
            {activeTab === "insider" && <InsiderTab insider={latest.sub_reports?.insider} />}
            {activeTab === "institutional" && <InstitutionalTab institutional={latest.sub_reports?.institutional} />}
            {activeTab === "sentiment" && <SentimentTab sentiment={latest.sub_reports?.sentiment} />}
            {activeTab === "ai-summary" && <AISummaryTab analysis={latest} />}
          </div>
        </>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">
        {title}
      </h2>
      {children}
    </section>
  );
}

function OverviewTab({ analysis }: { analysis: Analysis }) {
  const pm = analysis.position_management;
  return (
    <div className="space-y-4">
      <Section title="Verdict">
        <p className="leading-relaxed text-zinc-200">{analysis.summary}</p>
      </Section>

      {analysis.key_trends.length > 0 && (
        <Section title="Key Trends">
          <ul className="space-y-1.5 text-sm text-zinc-300">
            {analysis.key_trends.map((t) => (
              <li key={t} className="flex gap-2">
                <span className="text-sky-400">▸</span> {t}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {analysis.flags.length > 0 && (
        <Section title="Flags">
          <ul className="space-y-1.5 text-sm text-amber-400">
            {analysis.flags.map((f) => (
              <li key={f}>⚑ {f}</li>
            ))}
          </ul>
        </Section>
      )}

      {pm && (
        <Section title="Position Management">
          <div className="grid gap-4 text-sm sm:grid-cols-2">
            <div>
              <p className="mb-1 text-zinc-500">Stair-step stops</p>
              <p className="font-mono text-zinc-200">
                {pm.stair_step_stops.map((s) => s.toFixed(2)).join("  ·  ")}
              </p>
            </div>
            <div>
              <p className="mb-1 text-zinc-500">Sizing</p>
              <p className="text-zinc-200">{pm.position_sizing}</p>
            </div>
            <div className="sm:col-span-2">
              <p className="mb-1 text-zinc-500">Trailing stop</p>
              <p className="text-zinc-200">{pm.trailing_stop_recommendation}</p>
            </div>
          </div>
        </Section>
      )}
    </div>
  );
}

function AISummaryTab({ analysis }: { analysis: Analysis }) {
  const { technical, fundamental, recommendation } = analysis.sub_reports ?? {};
  // Market-wide, so it isn't part of the per-ticker analysis payload.
  const { data: breadth } = useMarketBreadth();
  return (
    <div className="space-y-4">
      {technical && (
        <Section
          title={`Technical — ${technical.overall_technical_signal} (${technical.confidence})`}
        >
          <div className="space-y-3 text-sm leading-relaxed text-zinc-300">
            <p>{technical.momentum_summary}</p>
            <p>{technical.tfc_narrative}</p>
            <p>{technical.bf_position_narrative}</p>
            <p>{technical.volume_narrative}</p>
            {technical.key_levels && (
              <p className="font-mono text-xs text-zinc-400">
                support {technical.key_levels.support.join(" / ")} · resistance{" "}
                {technical.key_levels.resistance.join(" / ")}
              </p>
            )}
          </div>
        </Section>
      )}

      {fundamental && (
        <Section
          title={`Fundamental — ${fundamental.overall_fundamental_signal} (${fundamental.confidence})`}
        >
          <p className="mb-3 text-sm leading-relaxed text-zinc-300">
            {fundamental.narrative}
          </p>
          <div className="flex flex-wrap gap-2 text-xs">
            {fundamental.revenue_trend && (
              <span className="rounded-full bg-zinc-800 px-2.5 py-1 text-zinc-300">
                revenue: {fundamental.revenue_trend.direction}
              </span>
            )}
            {fundamental.margin_trend && (
              <span className="rounded-full bg-zinc-800 px-2.5 py-1 text-zinc-300">
                margins: {fundamental.margin_trend.direction}
              </span>
            )}
            {fundamental.balance_sheet_health && (
              <span className="rounded-full bg-zinc-800 px-2.5 py-1 text-zinc-300">
                balance sheet: {fundamental.balance_sheet_health.assessment}
              </span>
            )}
            {fundamental.fcf_profile && (
              <span className="rounded-full bg-zinc-800 px-2.5 py-1 text-zinc-300">
                FCF: {fundamental.fcf_profile.assessment}
              </span>
            )}
          </div>
        </Section>
      )}

      {recommendation && (
        <Section title={`Market Timing — ${recommendation.recommendation}`}>
          <p className="mb-2 text-sm leading-relaxed text-zinc-300">
            {recommendation.rationale}
          </p>
          <p className="text-xs text-zinc-500">
            NYMO {recommendation.nymo_current ?? "–"} ({recommendation.nymo_signal}) ·
            NAMO {recommendation.namo_current ?? "–"}
          </p>
          {/* The rationale often cites a SPY/NYMO divergence — show it rather
              than only describing it. Rendered whenever breadth data exists, so
              the relationship stays inspectable with no divergence in force. */}
          {breadth && (
            <div className="mt-3">
              <BreadthDivergenceChart breadth={breadth} />
            </div>
          )}
          {recommendation.caveats.length > 0 && (
            <ul className="mt-2 space-y-1 text-xs text-amber-400/90">
              {recommendation.caveats.map((c) => (
                <li key={c}>⚠ {c}</li>
              ))}
            </ul>
          )}
        </Section>
      )}
    </div>
  );
}

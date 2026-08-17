// Spec: specs/component-specs/frontend/pages/StockDetail.md
// Reorganized by specs/021-stock-page-redesign: all chart content lives in the
// Charts tab (the default), the always-on TFC grid and Deep Dive block are gone.
import { useEffect } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import type { Analysis, ChangesSinceLast } from "../api/types";
import ConvictionMeter from "../components/shared/ConvictionMeter";
import SignalBadge from "../components/shared/SignalBadge";
import ChartsTab from "../components/stock/ChartsTab";
import FormattedProse from "../components/stock/FormattedProse";
import NewsTab from "../components/stock/NewsTab";
import FullRefreshButton from "../components/stock/FullRefreshButton";
import PullCostPanel from "../components/stock/PullCostPanel";
import {
  FundamentalsTab,
  InsiderTab,
  InstitutionalTab,
  SentimentTab,
  TechnicalsTab,
} from "../components/stock/tabs";
import { useTickerAnalysis, useTickerRecord } from "../hooks/useAnalysis";
import { usePullMetrics } from "../hooks/usePullMetrics";
import { useStockPriceHistory } from "../hooks/usePriceHistory";
import { useEnqueueTicker, useQueueStatus } from "../hooks/useQueue";
import { useAddToWatchlist } from "../hooks/useWatchlist";
import { PANEL_TIMEFRAMES } from "../lib/strat/displayWindow";
import { formatDate, relativeTime } from "../lib/time";

const TABS = [
  { id: "charts", label: "Charts" },
  { id: "overview", label: "Overview" },
  { id: "technicals", label: "Technicals" },
  { id: "fundamentals", label: "Fundamentals" },
  { id: "insider", label: "Insider" },
  { id: "institutional", label: "Institutional" },
  { id: "news", label: "News" },
  { id: "sentiment", label: "Sentiment" },
  { id: "ai-summary", label: "AI Summary" },
];

const DEFAULT_TAB = "charts";

export default function StockDetail() {
  const { ticker = "" } = useParams<{ ticker: string }>();
  const symbol = ticker.toUpperCase();
  const location = useLocation();
  const navigate = useNavigate();
  // Unknown/removed anchors fall back to Charts so old deep links still resolve (FR-027)
  const hash = location.hash.replace("#", "");
  const activeTab = TABS.some((t) => t.id === hash) ? hash : DEFAULT_TAB;

  const { data: analysis, isLoading } = useTickerAnalysis(symbol);
  const { data: record } = useTickerRecord(symbol);
  const { data: queue } = useQueueStatus();
  const { data: priceData } = useStockPriceHistory(symbol, PANEL_TIMEFRAMES);
  const { data: pullMetrics } = usePullMetrics(symbol);
  const enqueue = useEnqueueTicker();
  const addToWatchlist = useAddToWatchlist();

  useEffect(() => {
    document.title = `StockAI — ${symbol}`;
  }, [symbol]);

  const latest = analysis ?? undefined;
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
              {queuedJob.mode === "full" ? "full refresh — " : ""}
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
          <FullRefreshButton
            ticker={symbol}
            onRefresh={() => enqueue.mutate({ ticker: symbol, mode: "full" })}
            busy={queuedJob?.status === "running"}
            pending={enqueue.isPending}
            hasData={!!latest}
          />
          <button
            onClick={() => addToWatchlist.mutate(symbol)}
            className="rounded-lg border border-zinc-700 px-4 py-1.5 text-sm text-zinc-300 transition-colors hover:border-zinc-500"
          >
            + Watchlist
          </button>
        </div>
      </div>

      {/* Diagnostic, collapsed to a single line — sits next to the button that
          produced it so pull cost is answerable where pulls are triggered (024
          US1, research D10). */}
      {pullMetrics?.pulls?.[0] && (
        <div className="mb-4">
          <PullCostPanel pull={pullMetrics.pulls[0]} />
        </div>
      )}

      {isLoading && <p className="py-12 text-center text-zinc-500">loading…</p>}

      {/* Compact rather than full-page: the Charts tab below still works
          without an analysis, so this shouldn't push it off screen. */}
      {!isLoading && !latest && (
        <div className="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/60 px-4 py-3 text-sm text-zinc-400">
          <span>{`No analysis yet for ${symbol} — charts below still render.`}</span>
          {queuedJob ? (
            <span className="text-sky-400">
              Analysis {queuedJob.status === "running" ? "running now" : "queued"} — this page
              updates when it lands.
            </span>
          ) : (
            <button
              onClick={() => enqueue.mutate(symbol)}
              className="rounded-lg bg-sky-600 px-3 py-1 text-xs font-medium text-white hover:bg-sky-500"
            >
              Pull Analysis ▶
            </button>
          )}
        </div>
      )}

      {/* Tabs render whenever there's price data — charts don't need an
          analysis (FR-009); analysis-backed tabs show their own empty states. */}
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
        {latest && (
          <span className="ml-auto self-center text-xs text-zinc-600">
            analyzed {relativeTime(latest.timestamp)}
            {formatDate(latest.timestamp) && ` — data as of ${formatDate(latest.timestamp)}`}
          </span>
        )}
      </nav>

      <div className="mt-6">
        {activeTab === "charts" && (
          <ChartsTab
            priceData={priceData}
            tfcStatus={latest?.sub_reports?.technical?.strat_result?.tfc?.status}
          />
        )}
        {activeTab !== "charts" &&
          (latest ? (
            <>
              {activeTab === "overview" && <OverviewTab analysis={latest} />}
              {activeTab === "technicals" && <TechnicalsTab technical={latest.sub_reports?.technical} />}
              {activeTab === "fundamentals" && <FundamentalsTab fundamental={latest.sub_reports?.fundamental} ticker={ticker} />}
              {activeTab === "insider" && <InsiderTab insider={latest.sub_reports?.insider} />}
              {activeTab === "institutional" && <InstitutionalTab institutional={latest.sub_reports?.institutional} />}
              {activeTab === "news" && <NewsTab news={latest.sub_reports?.news} />}
              {activeTab === "sentiment" && (
                <SentimentTab sentiment={latest.sub_reports?.sentiment} news={latest.sub_reports?.news} />
              )}
              {activeTab === "ai-summary" && <AISummaryTab analysis={latest} />}
            </>
          ) : (
            !isLoading && (
              <p className="py-12 text-center text-sm text-zinc-600">
                No analysis yet — pull one to populate this tab.
              </p>
            )
          ))}
      </div>
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
  // Position Management is intentionally not rendered here (spec 021 FR-011);
  // the payload still ships on the analysis for other consumers (spec 015).
  return (
    <div className="space-y-4">
      <Section title="Verdict">
        <FormattedProse text={analysis.summary} />
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

    </div>
  );
}

const STANCE_STYLES: Record<string, string> = {
  bullish: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  neutral: "border-zinc-700 bg-zinc-800 text-zinc-300",
  bearish: "border-red-500/30 bg-red-500/10 text-red-400",
};

function ChangesSinceLastNote({ changes }: { changes: ChangesSinceLast }) {
  const moved = changes.signal.changed || changes.conviction.changed;
  const hasFlagChanges = changes.flags_added.length > 0 || changes.flags_removed.length > 0;

  return (
    <div className="space-y-2 text-sm text-zinc-300">
      {!moved && !hasFlagChanges && (
        <p className="text-zinc-500">
          No material change since the previous analysis — signal, conviction, and flags all held.
        </p>
      )}
      {changes.signal.changed && (
        <p>
          Signal moved from <span className="text-zinc-400">{changes.signal.from}</span> to{" "}
          <span className="font-medium text-zinc-100">{changes.signal.to}</span>.
        </p>
      )}
      {changes.conviction.changed && (
        <p>
          Conviction moved from <span className="text-zinc-400">{changes.conviction.from}</span> to{" "}
          <span className="font-medium text-zinc-100">{changes.conviction.to}</span>.
        </p>
      )}
      {changes.flags_added.length > 0 && (
        <p className="text-amber-400/90">New flags: {changes.flags_added.join("; ")}</p>
      )}
      {changes.flags_removed.length > 0 && (
        <p className="text-zinc-500">Cleared: {changes.flags_removed.join("; ")}</p>
      )}
      <p className="text-xs text-zinc-600">
        compared against the analysis from{" "}
        {formatDate(changes.previous_timestamp) || changes.previous_timestamp}
      </p>
    </div>
  );
}

function AISummaryTab({ analysis }: { analysis: Analysis }) {
  const { technical, fundamental, recommendation, news } = analysis.sub_reports ?? {};
  const changes = analysis.changes_since_last;
  return (
    <div className="space-y-4">
      {changes && (
        <Section title="What changed since the last analysis">
          <ChangesSinceLastNote changes={changes} />
        </Section>
      )}

      {news?.stance && (
        <Section title={`News stance — ${news.stance.direction}`}>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full border px-2.5 py-0.5 text-xs ${
                STANCE_STYLES[news.stance.direction] ?? STANCE_STYLES.neutral
              }`}
            >
              {news.stance.direction}
            </span>
            <span className="text-xs text-zinc-600">
              from {news.news_count} recent {news.news_count === 1 ? "article" : "articles"}
              {news.as_of && ` — most recent ${formatDate(news.as_of) || news.as_of}`}
            </span>
          </div>
          <FormattedProse text={news.stance.reasoning} />
        </Section>
      )}

      {technical && (
        <Section
          title={`Technical — ${technical.overall_technical_signal} (${technical.confidence})`}
        >
          <div className="space-y-4">
            <FormattedProse text={technical.momentum_summary} />
            <FormattedProse text={technical.tfc_narrative} />
            <FormattedProse text={technical.bf_position_narrative} />
            <FormattedProse text={technical.volume_narrative} />
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
          <FormattedProse text={fundamental.narrative} className="mb-3" />
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
          {/* The breadth/divergence chart lives on the Macro page — repeating
              it here was duplicate information (spec 021 FR-023). The caveats
              below are the part that's specific to this ticker. */}
          <FormattedProse text={recommendation.rationale} className="mb-2" />
          <p className="text-xs text-zinc-500">
            NYMO {recommendation.nymo_current ?? "–"} ({recommendation.nymo_signal}) ·
            NAMO {recommendation.namo_current ?? "–"}
          </p>
          {recommendation.caveats.length > 0 && (
            <ul className="mt-3 space-y-1.5 text-xs text-amber-400/90">
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

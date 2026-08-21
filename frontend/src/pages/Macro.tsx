// Spec: specs/component-specs/frontend/pages/Macro.md
//
// A market-wide dashboard, decoupled from any single ticker's analysis
// (specs/026-macro-market-dashboard): breadth, then the yield curve, then the
// economic calendar, then the standing indicator backdrop (FR-005) —
// decreasing time-sensitivity, top to bottom. The breadth panel is the page's
// one permanent market-flow visualization (FR-002a): it renders whenever
// breadth data exists, decorated by the most recent *active* market-flow
// event when one exists, but its existence never depends on one.
//
// Per-sector macro commentary previously lived on this page; it has moved
// off (FR-003) — the system still produces and serves it via GET /market/macro
// for a future Sectors page (FR-004), this page just stops consuming it.
import { type ReactNode, useEffect } from "react";
import MarketFlowCard from "../components/feed/MarketFlowCard";
import EconomicCalendarPanel from "../components/macro/EconomicCalendarPanel";
import IndicatorTiles from "../components/macro/IndicatorTiles";
import SpreadTiles from "../components/macro/SpreadTiles";
import YieldCurveChart from "../components/macro/YieldCurveChart";
import {
  useEconomicCalendar,
  useEconomicIndicators,
  useRiskPremium,
  useTreasuryCurve,
} from "../hooks/useEconomics";
import { useMarketBreadth, useMarketFlowEvents } from "../hooks/useMarketBreadth";
import { relativeTime } from "../lib/time";
import type { Freshness } from "../api/types";

// How recent a market-flow event must be to still count as "active" and
// decorate the breadth panel — distinct from whether the panel itself
// renders, which depends only on breadth data existing (FR-002a).
const MARKET_EVENT_MAX_AGE_DAYS = 14;

/** Shared chrome for every section below breadth: a title and an as-of/stale
 * indicator (FR-006, FR-028) — the section's own content decides what to
 * show when the data itself is empty or partial. */
function Section({
  title,
  freshness,
  children,
}: {
  title: string;
  freshness?: Freshness;
  children: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">{title}</h2>
        {freshness && (
          <span className="text-xs text-zinc-500">
            {freshness.as_of ? relativeTime(freshness.as_of) : "not computed yet"}
            {freshness.stale && <span className="ml-1 text-amber-400">· stale</span>}
          </span>
        )}
      </div>
      {children}
    </section>
  );
}

export default function Macro() {
  const { data: marketEvents } = useMarketFlowEvents();
  const { data: breadth, isLoading: breadthLoading } = useMarketBreadth();
  const { data: curve, isLoading: curveLoading } = useTreasuryCurve();
  const { data: calendar, isLoading: calendarLoading } = useEconomicCalendar();
  const { data: indicators, isLoading: indicatorsLoading } = useEconomicIndicators();
  const { data: riskPremium } = useRiskPremium();

  useEffect(() => {
    document.title = "StockAI — Macro";
  }, []);

  const cutoff = Date.now() - MARKET_EVENT_MAX_AGE_DAYS * 86_400_000;
  const activeEvent = (marketEvents ?? []).find(
    (e) => new Date(e.created_at).getTime() >= cutoff,
  );

  // FR-031: a single explanatory empty state, only once every section's
  // query has settled with nothing to show — never four separate error
  // boxes, and never a flash of "no data" while queries are still loading.
  const allSettled = !breadthLoading && !curveLoading && !calendarLoading && !indicatorsLoading;
  const isEmpty = allSettled && !breadth && !curve && !calendar && !indicators;

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-white">Macro</h1>
      </div>

      {breadth && <MarketFlowCard event={activeEvent} breadth={breadth} />}

      {curve && (
        <Section title="Rates & yield curve" freshness={curve}>
          <YieldCurveChart data={curve} />
          <div className="mt-4">
            <SpreadTiles spreads={curve.spreads} />
          </div>
        </Section>
      )}

      {calendar && (
        <Section title="Economic calendar" freshness={calendar}>
          <EconomicCalendarPanel upcoming={calendar.upcoming} reported={calendar.reported} />
        </Section>
      )}

      {indicators && (
        <Section title="Growth, inflation & risk backdrop" freshness={indicators}>
          <IndicatorTiles indicators={indicators.indicators} riskPremium={riskPremium} />
        </Section>
      )}

      {isEmpty && (
        <div className="py-16 text-center text-zinc-500">
          <p className="mb-1 text-lg text-zinc-400">No macro data yet</p>
          <p className="text-sm">
            Data appears here after the first refresh runs — check back soon.
          </p>
        </div>
      )}
    </div>
  );
}

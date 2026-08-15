// Spec: specs/component-specs/frontend/pages/Macro.md
//
// Economy-wide context, decoupled from any single ticker's analysis
// (specs/020-surface-macro-ui): market-breadth (NYMO/NAMO) divergence cards —
// relocated here from the Stocks page — plus every sector's macro read,
// produced independently by the agent-runner's macro worker.
import { useEffect } from "react";
import SignalBadge from "../components/shared/SignalBadge";
import MarketFlowCard from "../components/feed/MarketFlowCard";
import BreadthDivergenceChart from "../components/stock/BreadthDivergenceChart";
import { useMacroReads } from "../hooks/useMacro";
import { useMarketBreadth, useMarketFlowEvents } from "../hooks/useMarketBreadth";
import { relativeTime } from "../lib/time";
import type { SectorMacroRead } from "../api/types";

const MARKET_EVENT_MAX_AGE_DAYS = 14;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">{title}</h2>
      {children}
    </section>
  );
}

function SectorCard({ read }: { read: SectorMacroRead }) {
  return (
    <Section title={read.sector}>
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <SignalBadge signal={read.overall_macro_signal} />
          <span className="text-xs text-zinc-500">confidence: {read.confidence}</span>
        </div>
        <span className="text-xs text-zinc-600">{relativeTime(read.computed_at)}</span>
      </div>
      <div className="space-y-2 text-sm leading-relaxed text-zinc-300">
        <p>
          <span className="text-zinc-500">Inflation ({read.inflation_impact.trend}) — </span>
          {read.inflation_impact.impact_on_sector}
        </p>
        <p>
          <span className="text-zinc-500">Rates ({read.rate_impact.direction}) — </span>
          {read.rate_impact.impact_on_valuation}
        </p>
        <p>
          <span className="text-zinc-500">Growth (recession: {read.growth_backdrop.recession_signal}) — </span>
          {read.growth_backdrop.commentary}
        </p>
        <p>
          <span className="text-zinc-500">Consumer — </span>
          {read.consumer_backdrop}
        </p>
        <p>
          <span className="text-zinc-500">Rotation — </span>
          {read.sector_rotation_signal}
        </p>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-zinc-500">
        {read.inflation_impact.cpi_latest != null && <span>CPI {read.inflation_impact.cpi_latest}</span>}
        {read.rate_impact.fed_funds_rate != null && <span>Fed funds {read.rate_impact.fed_funds_rate}%</span>}
        {read.growth_backdrop.yield_curve_spread != null && (
          <span>
            10y-2y spread {read.growth_backdrop.yield_curve_spread}
            {read.growth_backdrop.curve_inverted ? " (inverted)" : ""}
          </span>
        )}
      </div>
    </Section>
  );
}

export default function Macro() {
  const { data: macro, isLoading } = useMacroReads();
  const { data: marketEvents } = useMarketFlowEvents();
  const { data: breadth } = useMarketBreadth();

  useEffect(() => {
    document.title = "StockAI — Macro";
  }, []);

  const cutoff = Date.now() - MARKET_EVENT_MAX_AGE_DAYS * 86_400_000;
  const pinnedEvents = (marketEvents ?? []).filter(
    (e) => new Date(e.created_at).getTime() >= cutoff,
  );
  const sectors = macro?.sectors ?? [];
  const isEmpty = !isLoading && pinnedEvents.length === 0 && sectors.length === 0 && !breadth;

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-white">Macro</h1>
        {macro?.as_of && (
          <p className="text-xs text-zinc-500">latest read {relativeTime(macro.as_of)}</p>
        )}
      </div>

      {pinnedEvents.length > 0 && (
        <div className="space-y-3">
          {pinnedEvents.map((event) => (
            <MarketFlowCard key={event.event_id} event={event} breadth={breadth} />
          ))}
        </div>
      )}

      {breadth && (
        <Section title="Market breadth">
          <BreadthDivergenceChart breadth={breadth} />
        </Section>
      )}

      {sectors.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2">
          {sectors.map((read) => (
            <SectorCard key={read.sector} read={read} />
          ))}
        </div>
      )}

      {isEmpty && (
        <div className="py-16 text-center text-zinc-500">
          <p className="mb-1 text-lg text-zinc-400">No macro data yet</p>
          <p className="text-sm">
            Macro reads appear here after the first refresh runs — check back soon.
          </p>
        </div>
      )}
    </div>
  );
}

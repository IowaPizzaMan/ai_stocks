// Stock Detail tab content: Technicals / Fundamentals / Insider / Institutional / Sentiment.
// Specs: specs/component-specs/frontend/components/stock/*.md (Phase 5 scope)
import type {
  FundamentalReport,
  InsiderReport,
  InstitutionalReport,
  SentimentReport,
  TechnicalReport,
} from "../../api/types";
import { useStockFinancials } from "../../hooks/usePriceHistory";
import { formatDate } from "../../lib/time";
import DataAsOf from "../shared/DataAsOf";
import FundamentalsCharts from "./FundamentalsCharts";

export function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">{title}</h2>
      {children}
    </section>
  );
}

function Pill({ children }: { children: React.ReactNode }) {
  return <span className="rounded-full bg-zinc-800 px-2.5 py-1 text-xs text-zinc-300">{children}</span>;
}

function Empty({ what }: { what: string }) {
  return <p className="py-8 text-center text-sm text-zinc-600">No {what} in the latest analysis — pull a fresh one.</p>;
}

// --- Technicals --------------------------------------------------------------

export function TechnicalsTab({ technical }: { technical?: TechnicalReport }) {
  if (!technical) return <Empty what="technical sub-report" />;
  const strat = technical.strat_result as
    | {
        timeframes?: Record<string, { last_bar: string; sequence: string[]; candle_color: string; patterns: { name: string; direction: string; note?: string }[] }>;
        tfc?: { status: string; last_sale?: number } & Record<string, unknown>;
      }
    | undefined;
  const accumulation = technical.accumulation_result;
  const gap = technical.gap_result as
    | { latest_gap?: Record<string, unknown> | null; peg?: Record<string, unknown> | null; signal?: string }
    | undefined;

  return (
    <div className="space-y-4">
      {strat?.timeframes && (
        <Section title="The Strat — bar types & patterns">
          <div className="grid gap-4 sm:grid-cols-3">
            {Object.entries(strat.timeframes).map(([tf, info]) => (
              <div key={tf} className="rounded-lg bg-zinc-950/60 p-3">
                <p className="mb-1 text-xs font-medium capitalize text-zinc-400">{tf}</p>
                <p className="font-mono text-sm text-zinc-200">
                  {info.sequence.join(" → ")}
                  <span className={`ml-2 ${info.candle_color === "green" ? "text-emerald-400" : "text-red-400"}`}>●</span>
                </p>
                {info.patterns.length > 0 ? (
                  <ul className="mt-2 space-y-1 text-xs text-zinc-300">
                    {info.patterns.map((p) => (
                      <li key={p.name}>
                        <span className={p.direction === "long" ? "text-emerald-400" : p.direction === "short" ? "text-red-400" : "text-zinc-400"}>
                          {p.name.replaceAll("_", " ")}
                        </span>
                        {p.note && <span className="text-zinc-500"> — {p.note}</span>}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-xs text-zinc-600">no active patterns</p>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      <Section title="Narratives">
        <DataAsOf date={technical.as_of} className="mb-3 text-xs text-zinc-600" />
        <div className="space-y-3 text-sm leading-relaxed text-zinc-300">
          <p><span className="text-zinc-500">Momentum — </span>{technical.momentum_summary}</p>
          <p><span className="text-zinc-500">TFC — </span>{technical.tfc_narrative}</p>
          <p><span className="text-zinc-500">Range — </span>{technical.bf_position_narrative}</p>
          <p><span className="text-zinc-500">Volume — </span>{technical.volume_narrative}</p>
        </div>
      </Section>

      <div className="grid gap-4 sm:grid-cols-2">
        {accumulation && (
          <Section title={`Accumulation — score ${accumulation.accumulation_score}/5`}>
            <p className="mb-2 text-sm text-zinc-300">{accumulation.signal}</p>
            {accumulation.rationale && <p className="text-xs text-zinc-500">{accumulation.rationale}</p>}
          </Section>
        )}
        <Section title="Gap picture">
          {gap?.latest_gap ? (
            <div className="space-y-1 text-sm text-zinc-300">
              <p>
                {String(gap.latest_gap.direction)}-gap ({String(gap.latest_gap.gap_type)}), score{" "}
                {String(gap.latest_gap.score)} — {String(gap.latest_gap.bias ?? "")}
              </p>
              <p className="text-xs text-zinc-500">{gap.signal}</p>
              {gap.peg != null && <Pill>PEG score {String((gap.peg as Record<string, unknown>).peg_score)}</Pill>}
            </div>
          ) : (
            <p className="text-sm text-zinc-500">no gaps in the lookback window</p>
          )}
        </Section>
      </div>

      {technical.key_levels && (
        <Section title="Key levels">
          <p className="font-mono text-sm text-zinc-300">
            support {technical.key_levels.support.join(" / ")} · resistance {technical.key_levels.resistance.join(" / ")}
          </p>
        </Section>
      )}
    </div>
  );
}

// --- Fundamentals ------------------------------------------------------------

export function FundamentalsTab({ fundamental, ticker }: { fundamental?: FundamentalReport; ticker: string }) {
  const { data: financials, isLoading } = useStockFinancials(ticker);

  if (!fundamental && !financials && !isLoading) return <Empty what="fundamental data" />;

  return (
    <div className="space-y-4">
      {fundamental && (
        <Section title="Assessment">
          <DataAsOf date={fundamental.as_of} label="latest statement" className="mb-3 text-xs text-zinc-600" />
          <p className="mb-3 text-sm leading-relaxed text-zinc-300">{fundamental.narrative}</p>
          <div className="flex flex-wrap gap-2">
            <Pill>revenue: {fundamental.revenue_trend?.direction}</Pill>
            <Pill>margins: {fundamental.margin_trend?.direction}</Pill>
            <Pill>balance sheet: {fundamental.balance_sheet_health?.assessment}</Pill>
            <Pill>FCF: {fundamental.fcf_profile?.assessment}</Pill>
            <Pill>valuation: {fundamental.valuation_assessment?.view}</Pill>
          </div>
        </Section>
      )}

      {financials ? (
        <FundamentalsCharts financials={financials} />
      ) : (
        !isLoading && <Empty what="cached financial statements" />
      )}
    </div>
  );
}

// --- Insider -----------------------------------------------------------------

export function InsiderTab({ insider }: { insider?: InsiderReport }) {
  if (!insider) return <Empty what="insider sub-report" />;
  return (
    <div className="space-y-4">
      <Section title={`Read — ${insider.overall_insider_signal} (${insider.signal_strength})`}>
        <DataAsOf date={insider.as_of} label="most recent transaction" className="mb-3 text-xs text-zinc-600" />
        <p className="mb-3 text-sm leading-relaxed text-zinc-300">{insider.narrative}</p>
        <div className="flex flex-wrap gap-2">
          <Pill>net: {insider.net_direction.replaceAll("_", " ")}</Pill>
          <Pill>MSPR: {insider.mspr_trend.direction.replaceAll("_", " ")}</Pill>
          {insider.cluster_signal.detected && (
            <span className="rounded-full bg-emerald-500/15 px-2.5 py-1 text-xs text-emerald-400">
              cluster buying: {insider.cluster_signal.insiders.length} insiders / {insider.cluster_signal.window_days}d
            </span>
          )}
        </div>
        {insider.key_buyers.length > 0 && (
          <ul className="mt-3 space-y-1 text-sm text-emerald-400/90">
            {insider.key_buyers.map((b) => <li key={b}>▸ {b}</li>)}
          </ul>
        )}
      </Section>

      <Section title="Transactions (90 days)">
        {insider.recent_transactions.length === 0 ? (
          <p className="text-sm text-zinc-500">no transactions reported</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-zinc-500">
                <tr>
                  <th className="pb-2 pr-4">Insider</th>
                  <th className="pb-2 pr-4">Type</th>
                  <th className="pb-2 pr-4 text-right">Shares</th>
                  <th className="pb-2 pr-4 text-right">Value</th>
                  <th className="pb-2">Date</th>
                </tr>
              </thead>
              <tbody className="text-zinc-300">
                {insider.recent_transactions.map((t, i) => (
                  <tr key={`${t.name}-${t.date}-${i}`} className="border-t border-zinc-800/60">
                    <td className="py-1.5 pr-4">{t.name}</td>
                    <td className={`py-1.5 pr-4 ${t.transaction_type === "purchase" ? "text-emerald-400" : t.transaction_type === "sale" ? "text-red-400" : "text-zinc-400"}`}>
                      {t.transaction_type.replaceAll("_", " ")}
                      {t.is_open_market ? "" : " *"}
                    </td>
                    <td className="py-1.5 pr-4 text-right font-mono">{t.shares.toLocaleString()}</td>
                    <td className="py-1.5 pr-4 text-right font-mono">
                      {t.total_value ? `$${Math.round(t.total_value).toLocaleString()}` : "–"}
                    </td>
                    <td className="py-1.5 text-zinc-500">{t.date}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-[10px] text-zinc-600">* not an open-market transaction (option exercise, award, gift...)</p>
          </div>
        )}
      </Section>
    </div>
  );
}

// --- Institutional -----------------------------------------------------------

export function InstitutionalTab({ institutional }: { institutional?: InstitutionalReport }) {
  if (!institutional) return <Empty what="institutional sub-report" />;
  const s = institutional.institutional_summary;
  return (
    <div className="space-y-4">
      <Section title={`Read — ${institutional.overall_institutional_signal}`}>
        <DataAsOf date={institutional.as_of} label="13F data as of" className="mb-3 text-xs text-zinc-600" />
        <p className="mb-3 text-sm leading-relaxed text-zinc-300">{institutional.narrative}</p>
        <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <div><p className="text-xs text-zinc-500">Ownership</p><p className="font-mono text-zinc-200">{s.ownership_pct ?? "–"}%</p></div>
          <div><p className="text-xs text-zinc-500">Institutions</p><p className="font-mono text-zinc-200">{s.institutions_count?.toLocaleString() ?? "–"}</p></div>
          <div><p className="text-xs text-zinc-500">Top-10 up / down</p><p className="font-mono text-zinc-200">{s.top10_increasing ?? "–"} / {s.top10_decreasing ?? "–"}</p></div>
          <div><p className="text-xs text-zinc-500">As of</p><p className="font-mono text-zinc-200">{s.as_of ?? "–"}</p></div>
        </div>
        <p className="mt-3 text-xs text-zinc-500">concentration: {institutional.concentration_assessment.replaceAll("_", " ")}</p>
      </Section>

      {(institutional.notable_increases.length > 0 || institutional.notable_reductions.length > 0) && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Section title="Notable increases">
            {institutional.notable_increases.length ? (
              <ul className="space-y-1 text-sm text-emerald-400/90">
                {institutional.notable_increases.map((x) => <li key={x}>▲ {x}</li>)}
              </ul>
            ) : <p className="text-sm text-zinc-600">none</p>}
          </Section>
          <Section title="Notable reductions">
            {institutional.notable_reductions.length ? (
              <ul className="space-y-1 text-sm text-red-400/90">
                {institutional.notable_reductions.map((x) => <li key={x}>▼ {x}</li>)}
              </ul>
            ) : <p className="text-sm text-zinc-600">none</p>}
          </Section>
        </div>
      )}

      <Section title="Superinvestors (Dataroma)">
        {institutional.superinvestor_available ? (
          institutional.superinvestor_moves.length ? (
            <ul className="space-y-1 text-sm text-zinc-300">
              {institutional.superinvestor_moves.map((m, i) => (
                <li key={i}>{m.fund} — {m.action}{m.detail ? ` (${m.detail})` : ""}</li>
              ))}
            </ul>
          ) : <p className="text-sm text-zinc-500">no recent moves in this name</p>
        ) : (
          <p className="text-sm text-zinc-600">{institutional.superinvestor_read || "data unavailable this run"}</p>
        )}
      </Section>
    </div>
  );
}

// --- Sentiment ---------------------------------------------------------------

export function SentimentTab({ sentiment }: { sentiment?: SentimentReport }) {
  if (!sentiment) return <Empty what="sentiment sub-report" />;
  return (
    <div className="space-y-4">
      <Section title={`Tone — ${sentiment.current_tone.replaceAll("_", " ")} (${sentiment.overall_sentiment_signal.replaceAll("_", " ")})`}>
        <p className="mb-3 text-sm leading-relaxed text-zinc-300">{sentiment.narrative}</p>
        {sentiment.tone_evidence.length > 0 && (
          <ul className="space-y-1 text-sm text-zinc-400">
            {sentiment.tone_evidence.map((e) => <li key={e}>▸ {e}</li>)}
          </ul>
        )}
        <p className="mt-3 text-xs text-zinc-600">
          based on {sentiment.news_count} headlines over 30 days
          {formatDate(sentiment.as_of ?? "") && `, most recent ${formatDate(sentiment.as_of ?? "")}`}
          {sentiment.transcripts_available ? "" : " (earnings-call transcripts unavailable on the current data plan)"}
        </p>
      </Section>

      <div className="grid gap-4 sm:grid-cols-2">
        <Section title={`Bullish language (${sentiment.bullish_keywords.count})`}>
          <div className="flex flex-wrap gap-1.5">
            {sentiment.bullish_keywords.terms.length
              ? sentiment.bullish_keywords.terms.map((t) => (
                  <span key={t} className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-400">{t}</span>
                ))
              : <span className="text-sm text-zinc-600">none detected</span>}
          </div>
        </Section>
        <Section title={`Cautious language (${sentiment.cautious_keywords.count})`}>
          <div className="flex flex-wrap gap-1.5">
            {sentiment.cautious_keywords.terms.length
              ? sentiment.cautious_keywords.terms.map((t) => (
                  <span key={t} className="rounded-full bg-amber-500/10 px-2 py-0.5 text-xs text-amber-400">{t}</span>
                ))
              : <span className="text-sm text-zinc-600">none detected</span>}
          </div>
        </Section>
      </div>

      <Section title="Earnings surprises">
        <p className="text-sm text-zinc-300">{sentiment.earnings_surprise_read}</p>
      </Section>
    </div>
  );
}

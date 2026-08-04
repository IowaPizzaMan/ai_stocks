// Numeric fundamentals chart sections, driven by the raw FMP payload from
// GET /stocks/{ticker}/financials (useStockFinancials). Rendered by
// FundamentalsTab below the LLM assessment. Spec: FundamentalsTab.md.
//
// Chart conventions: single y-axis per panel (measures on different scales get
// their own panel, never a second axis); 4-slot categorical palette validated
// for CVD separation + contrast on the zinc-900 surface; series identity always
// carried by a legend, values by tooltip/axis.
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { StockFinancials } from "../../api/types";
import { CHART_DEFAULTS } from "../../lib/constants";
import MetricCard from "../shared/MetricCard";

// Fixed categorical order — assigned in sequence, never cycled.
// Validated (dataviz six checks) against surface #18181b: worst adjacent
// CVD ΔE 10.1, normal-vision 28.8, all ≥3:1 contrast.
const S1 = "#0284c7"; // sky-600
const S2 = "#ea580c"; // orange-600
const S3 = "#059669"; // emerald-600
const S4 = "#7c3aed"; // violet-600

const tooltipStyle = {
  contentStyle: { backgroundColor: "#09090b", border: "1px solid #27272a", borderRadius: 8, fontSize: 12 },
  labelStyle: { color: "#a1a1aa" },
};

const axisTick = { fill: CHART_DEFAULTS.textColor, fontSize: 11 };

function fmtB(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1e12) return `$${(v / 1e12).toFixed(1)}T`;
  if (abs >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${v.toFixed(0)}`;
}

function fmtPct(v: number): string {
  return `${v.toFixed(1)}%`;
}

function ChartSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">{title}</h2>
      {children}
    </section>
  );
}

function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
      {items.map((it) => (
        <span key={it.label} className="flex items-center gap-1.5 text-[11px] text-zinc-400">
          <span className="inline-block h-2 w-2 rounded-sm" style={{ backgroundColor: it.color }} />
          {it.label}
        </span>
      ))}
    </div>
  );
}

function Caption({ children }: { children: React.ReactNode }) {
  return <p className="mt-2 text-[11px] leading-snug text-zinc-500">{children}</p>;
}

// FMP arrays come newest-first; charts want chronological.
function chrono<T extends { date: string }>(rows: T[] | undefined): T[] {
  return [...(rows ?? [])].reverse();
}

function yearOf(date: string): string {
  return date.slice(0, 4);
}

const pct = (v: number | null | undefined) => (v == null ? null : v * 100);

// ---------------------------------------------------------------------------

export default function FundamentalsCharts({ financials }: { financials: StockFinancials }) {
  const income = chrono(financials.income_annual);
  const incomeQ = chrono(financials.income_quarterly);
  const balance = chrono(financials.balance_annual);
  const cashflow = chrono(financials.cashflow_annual);
  const ratios = chrono(financials.ratios);
  const keyMetrics = chrono(financials.key_metrics);
  const growth = chrono(financials.growth);

  const latestRatios = financials.ratios?.[0];
  const prevRatios = financials.ratios?.[1];
  const latestKM = financials.key_metrics?.[0];
  const prevKM = financials.key_metrics?.[1];

  const trendOf = (latest: number | null | undefined, prev: number | null | undefined): "up" | "down" | "flat" => {
    if (latest == null || prev == null || latest === prev) return "flat";
    return latest > prev ? "up" : "down";
  };

  // Elevated-ROE guard: buybacks shrinking equity inflate ROE — caption it
  // instead of letting a 150% ROE read as a data error.
  const roeElevated = (latestKM?.returnOnEquity ?? 0) > 0.6;

  const growthData = growth.map((g) => ({
    year: yearOf(g.date),
    revenue: pct(g.growthRevenue),
    netIncome: pct(g.growthNetIncome),
    eps: pct(g.growthEPS),
  }));

  const marginData = ratios.map((r) => ({
    year: yearOf(r.date),
    gross: pct(r.grossProfitMargin),
    operating: pct(r.operatingProfitMargin),
    ebitda: pct(r.ebitdaMargin),
    net: pct(r.netProfitMargin),
  }));

  const returnsData = keyMetrics.map((k) => ({
    year: yearOf(k.date),
    roe: pct(k.returnOnEquity),
    roic: pct(k.returnOnInvestedCapital),
    roa: pct(k.returnOnAssets),
    roce: pct(k.returnOnCapitalEmployed),
  }));

  const cfQuality = cashflow.map((c, i) => ({
    year: yearOf(c.date),
    netIncome: c.netIncome ?? income[i]?.netIncome ?? null,
    ocf: c.operatingCashFlow,
    fcf: c.freeCashFlow,
  }));

  const capitalIntensity = cashflow.map((c) => ({
    year: yearOf(c.date),
    ocf: c.operatingCashFlow,
    capex: Math.abs(c.capitalExpenditure ?? 0),
    fcf: c.freeCashFlow,
  }));

  const payout = cashflow.map((c) => ({
    year: yearOf(c.date),
    buybacks: Math.abs(c.commonStockRepurchased ?? 0),
    dividends: Math.abs(c.commonDividendsPaid ?? 0),
    fcf: c.freeCashFlow,
  }));
  const overpaidYears = payout.filter((p) => p.buybacks + p.dividends > p.fcf).map((p) => p.year);

  const efficiency = keyMetrics.map((k) => ({
    year: yearOf(k.date),
    dso: k.daysOfSalesOutstanding,
    dio: k.daysOfInventoryOutstanding,
    dpo: k.daysOfPayablesOutstanding,
  }));
  const ccc = latestKM?.cashConversionCycle;

  const debtEquityData = ratios.map((r, i) => ({
    year: yearOf(r.date),
    de: r.debtToEquityRatio,
    totalDebt: balance[i]?.totalDebt ?? null,
  }));

  const liquidityBand = (v: number | null | undefined) =>
    v == null
      ? "text-zinc-500"
      : v < 1.0
        ? "text-red-400"
        : v < 1.5
          ? "text-amber-400"
          : "text-emerald-400";

  return (
    <div className="space-y-4">
      {/* 1 — Growth & scale */}
      {income.length > 0 && (
        <ChartSection title="Growth & scale">
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart data={income.map((r) => ({ year: yearOf(r.date), revenue: r.revenue, netIncome: r.netIncome }))}>
              <CartesianGrid stroke={CHART_DEFAULTS.gridColor} vertical={false} />
              <XAxis dataKey="year" tick={axisTick} tickLine={false} axisLine={false} />
              <YAxis tick={axisTick} tickLine={false} axisLine={false} width={52} tickFormatter={fmtB} />
              <Bar dataKey="revenue" name="Revenue" fill={S1} maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false} />
              <Bar dataKey="netIncome" name="Net income" fill={S3} maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false} />
              <Tooltip {...tooltipStyle} formatter={(v) => fmtB(Number(v))} />
            </ComposedChart>
          </ResponsiveContainer>
          <Legend items={[{ label: "Revenue", color: S1 }, { label: "Net income", color: S3 }]} />

          {growthData.length > 1 && (
            <>
              <ResponsiveContainer width="100%" height={140}>
                <ComposedChart data={growthData}>
                  <CartesianGrid stroke={CHART_DEFAULTS.gridColor} vertical={false} />
                  <XAxis dataKey="year" tick={axisTick} tickLine={false} axisLine={false} />
                  <YAxis tick={axisTick} tickLine={false} axisLine={false} width={52} tickFormatter={fmtPct} />
                  <ReferenceLine y={0} stroke={CHART_DEFAULTS.textColor} strokeWidth={1} />
                  <Line type="monotone" dataKey="revenue" name="Revenue YoY" stroke={S1} strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="netIncome" name="Net income YoY" stroke={S2} strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="eps" name="EPS YoY" stroke={S3} strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Tooltip {...tooltipStyle} formatter={(v) => fmtPct(Number(v))} />
                </ComposedChart>
              </ResponsiveContainer>
              <Legend items={[{ label: "Revenue YoY %", color: S1 }, { label: "Net income YoY %", color: S2 }, { label: "EPS YoY %", color: S3 }]} />
              <Caption>Growth panel sits below the bars (own scale) — watch for growth decelerating even while absolute $ climbs.</Caption>
            </>
          )}

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <p className="mb-1 text-xs text-zinc-500">EPS (diluted primary)</p>
              <ResponsiveContainer width="100%" height={130}>
                <ComposedChart data={income.map((r) => ({ year: yearOf(r.date), diluted: r.epsDiluted, basic: r.eps }))}>
                  <CartesianGrid stroke={CHART_DEFAULTS.gridColor} vertical={false} />
                  <XAxis dataKey="year" tick={axisTick} tickLine={false} axisLine={false} />
                  <YAxis tick={axisTick} tickLine={false} axisLine={false} width={40} />
                  <Line type="monotone" dataKey="diluted" name="Diluted" stroke={S1} strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="basic" name="Basic" stroke={S4} strokeWidth={1} dot={false} isAnimationActive={false} />
                  <Tooltip {...tooltipStyle} />
                </ComposedChart>
              </ResponsiveContainer>
              <Legend items={[{ label: "Diluted", color: S1 }, { label: "Basic", color: S4 }]} />
            </div>
            {incomeQ.length > 0 && (
              <div>
                <p className="mb-1 text-xs text-zinc-500">Quarterly revenue (seasonality)</p>
                <ResponsiveContainer width="100%" height={130}>
                  <ComposedChart data={incomeQ.map((r) => ({ q: `${r.period} '${yearOf(r.date).slice(2)}`, revenue: r.revenue }))}>
                    <CartesianGrid stroke={CHART_DEFAULTS.gridColor} vertical={false} />
                    <XAxis dataKey="q" tick={axisTick} tickLine={false} axisLine={false} />
                    <YAxis tick={axisTick} tickLine={false} axisLine={false} width={52} tickFormatter={fmtB} />
                    <Bar dataKey="revenue" name="Revenue" fill={S1} maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                    <Tooltip {...tooltipStyle} formatter={(v) => fmtB(Number(v))} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </ChartSection>
      )}

      {/* 2 — Margins */}
      {marginData.length > 0 && (
        <ChartSection title="Profitability — margins %">
          <ResponsiveContainer width="100%" height={200}>
            <ComposedChart data={marginData}>
              <CartesianGrid stroke={CHART_DEFAULTS.gridColor} vertical={false} />
              <XAxis dataKey="year" tick={axisTick} tickLine={false} axisLine={false} />
              <YAxis tick={axisTick} tickLine={false} axisLine={false} width={40} tickFormatter={fmtPct} />
              <Line type="monotone" dataKey="gross" name="Gross" stroke={S1} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="operating" name="Operating" stroke={S2} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="ebitda" name="EBITDA" stroke={S3} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="net" name="Net" stroke={S4} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Tooltip {...tooltipStyle} formatter={(v) => fmtPct(Number(v))} />
            </ComposedChart>
          </ResponsiveContainer>
          <Legend items={[{ label: "Gross", color: S1 }, { label: "Operating", color: S2 }, { label: "EBITDA", color: S3 }, { label: "Net", color: S4 }]} />
        </ChartSection>
      )}

      {/* 3 — Returns & capital efficiency */}
      {returnsData.length > 0 && (
        <ChartSection title="Returns & capital efficiency %">
          <ResponsiveContainer width="100%" height={200}>
            <ComposedChart data={returnsData}>
              <CartesianGrid stroke={CHART_DEFAULTS.gridColor} vertical={false} />
              <XAxis dataKey="year" tick={axisTick} tickLine={false} axisLine={false} />
              <YAxis tick={axisTick} tickLine={false} axisLine={false} width={40} tickFormatter={fmtPct} />
              <Line type="monotone" dataKey="roe" name="ROE" stroke={S1} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="roic" name="ROIC" stroke={S2} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="roa" name="ROA" stroke={S3} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="roce" name="ROCE" stroke={S4} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Tooltip {...tooltipStyle} formatter={(v) => fmtPct(Number(v))} />
            </ComposedChart>
          </ResponsiveContainer>
          <Legend items={[{ label: "ROE", color: S1 }, { label: "ROIC", color: S2 }, { label: "ROA", color: S3 }, { label: "ROCE", color: S4 }]} />
          {roeElevated && (
            <Caption>
              ⚠ ROE is elevated because buybacks have shrunk stockholders' equity (the denominator) — not a data error.
              Read ROIC/ROA for the cleaner efficiency signal.
            </Caption>
          )}
        </ChartSection>
      )}

      {/* 4 — Balance sheet health / liquidity */}
      {balance.length > 0 && (
        <ChartSection title="Balance sheet health">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <p className="mb-1 text-xs text-zinc-500">Current assets vs current liabilities</p>
              <ResponsiveContainer width="100%" height={160}>
                <ComposedChart data={balance.map((b) => ({ year: yearOf(b.date), assets: b.totalCurrentAssets, liabilities: b.totalCurrentLiabilities }))}>
                  <CartesianGrid stroke={CHART_DEFAULTS.gridColor} vertical={false} />
                  <XAxis dataKey="year" tick={axisTick} tickLine={false} axisLine={false} />
                  <YAxis tick={axisTick} tickLine={false} axisLine={false} width={52} tickFormatter={fmtB} />
                  <Bar dataKey="assets" name="Current assets" fill={S1} maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                  <Bar dataKey="liabilities" name="Current liabilities" fill={S2} maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                  <Tooltip {...tooltipStyle} formatter={(v) => fmtB(Number(v))} />
                </ComposedChart>
              </ResponsiveContainer>
              <Legend items={[{ label: "Current assets", color: S1 }, { label: "Current liabilities", color: S2 }]} />
            </div>
            <div>
              <p className="mb-1 text-xs text-zinc-500">Debt vs cash</p>
              <ResponsiveContainer width="100%" height={160}>
                <ComposedChart data={balance.map((b) => ({ year: yearOf(b.date), debt: b.totalDebt, cash: b.cashAndCashEquivalents, netDebt: b.netDebt }))}>
                  <CartesianGrid stroke={CHART_DEFAULTS.gridColor} vertical={false} />
                  <XAxis dataKey="year" tick={axisTick} tickLine={false} axisLine={false} />
                  <YAxis tick={axisTick} tickLine={false} axisLine={false} width={52} tickFormatter={fmtB} />
                  <Bar dataKey="debt" name="Total debt" fill={S2} maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                  <Bar dataKey="cash" name="Cash" fill={S3} maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                  <Line type="monotone" dataKey="netDebt" name="Net debt" stroke={S4} strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Tooltip {...tooltipStyle} formatter={(v) => fmtB(Number(v))} />
                </ComposedChart>
              </ResponsiveContainer>
              <Legend items={[{ label: "Total debt", color: S2 }, { label: "Cash", color: S3 }, { label: "Net debt", color: S4 }]} />
            </div>
          </div>

          {/* Liquidity ratios — paired with OCF ratio, which is the honest signal for fast-cash businesses */}
          {latestRatios && (
            <div className="mt-4 grid grid-cols-3 gap-3">
              {[
                { label: "Current ratio", value: latestRatios.currentRatio },
                { label: "Quick ratio", value: latestRatios.quickRatio },
                { label: "Op. cash flow ratio", value: latestRatios.operatingCashFlowRatio },
              ].map((m) => (
                <div key={m.label} className="rounded-lg bg-zinc-950/60 p-3">
                  <p className="text-xs text-zinc-500">{m.label}</p>
                  <p className={`text-xl font-semibold ${liquidityBand(m.value)}`}>
                    {m.value == null ? "—" : m.value.toFixed(2)}
                  </p>
                </div>
              ))}
            </div>
          )}
          <Caption>
            A current ratio under 1.0 isn't automatically alarming for fast cash-generating businesses — read it
            alongside the operating cash flow ratio.
          </Caption>

          {debtEquityData.length > 1 && (
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <p className="mb-1 text-xs text-zinc-500">Debt / equity</p>
                <ResponsiveContainer width="100%" height={120}>
                  <ComposedChart data={debtEquityData}>
                    <CartesianGrid stroke={CHART_DEFAULTS.gridColor} vertical={false} />
                    <XAxis dataKey="year" tick={axisTick} tickLine={false} axisLine={false} />
                    <YAxis tick={axisTick} tickLine={false} axisLine={false} width={36} />
                    <Line type="monotone" dataKey="de" name="Debt/equity" stroke={S1} strokeWidth={2} dot={false} isAnimationActive={false} />
                    <Tooltip {...tooltipStyle} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
              <div>
                <p className="mb-1 text-xs text-zinc-500">Total debt (the real story)</p>
                <ResponsiveContainer width="100%" height={120}>
                  <ComposedChart data={debtEquityData}>
                    <CartesianGrid stroke={CHART_DEFAULTS.gridColor} vertical={false} />
                    <XAxis dataKey="year" tick={axisTick} tickLine={false} axisLine={false} />
                    <YAxis tick={axisTick} tickLine={false} axisLine={false} width={52} tickFormatter={fmtB} />
                    <Line type="monotone" dataKey="totalDebt" name="Total debt" stroke={S2} strokeWidth={2} dot={false} isAnimationActive={false} />
                    <Tooltip {...tooltipStyle} formatter={(v) => fmtB(Number(v))} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
          <Caption>
            A falling debt/equity ratio can be equity shrinking from buybacks rather than de-leveraging — the total
            debt line alongside shows whether debt actually fell.
          </Caption>
        </ChartSection>
      )}

      {/* 5 — Cash flow quality */}
      {cfQuality.length > 0 && (
        <ChartSection title="Cash flow quality">
          <ResponsiveContainer width="100%" height={200}>
            <ComposedChart data={cfQuality}>
              <CartesianGrid stroke={CHART_DEFAULTS.gridColor} vertical={false} />
              <XAxis dataKey="year" tick={axisTick} tickLine={false} axisLine={false} />
              <YAxis tick={axisTick} tickLine={false} axisLine={false} width={52} tickFormatter={fmtB} />
              <Line type="monotone" dataKey="netIncome" name="Net income" stroke={S1} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="ocf" name="Operating CF" stroke={S2} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="fcf" name="Free CF" stroke={S3} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Tooltip {...tooltipStyle} formatter={(v) => fmtB(Number(v))} />
            </ComposedChart>
          </ResponsiveContainer>
          <Legend items={[{ label: "Net income", color: S1 }, { label: "Operating CF", color: S2 }, { label: "Free CF", color: S3 }]} />
          <Caption>
            The "is the accounting real" check — operating cash flow should track or exceed net income.
          </Caption>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <p className="mb-1 text-xs text-zinc-500">Capital intensity (OCF → capex → FCF)</p>
              <ResponsiveContainer width="100%" height={150}>
                <ComposedChart data={capitalIntensity}>
                  <CartesianGrid stroke={CHART_DEFAULTS.gridColor} vertical={false} />
                  <XAxis dataKey="year" tick={axisTick} tickLine={false} axisLine={false} />
                  <YAxis tick={axisTick} tickLine={false} axisLine={false} width={52} tickFormatter={fmtB} />
                  <Bar dataKey="ocf" name="Operating CF" fill={S1} maxBarSize={16} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                  <Bar dataKey="capex" name="Capex" fill={S2} maxBarSize={16} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                  <Bar dataKey="fcf" name="Free CF" fill={S3} maxBarSize={16} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                  <Tooltip {...tooltipStyle} formatter={(v) => fmtB(Number(v))} />
                </ComposedChart>
              </ResponsiveContainer>
              <Legend items={[{ label: "Operating CF", color: S1 }, { label: "Capex", color: S2 }, { label: "Free CF", color: S3 }]} />
            </div>
            <div>
              <p className="mb-1 text-xs text-zinc-500">Shareholder returns vs FCF</p>
              <ResponsiveContainer width="100%" height={150}>
                <ComposedChart data={payout}>
                  <CartesianGrid stroke={CHART_DEFAULTS.gridColor} vertical={false} />
                  <XAxis dataKey="year" tick={axisTick} tickLine={false} axisLine={false} />
                  <YAxis tick={axisTick} tickLine={false} axisLine={false} width={52} tickFormatter={fmtB} />
                  <Bar dataKey="buybacks" name="Buybacks" stackId="payout" fill={S2} maxBarSize={24} isAnimationActive={false} />
                  <Bar dataKey="dividends" name="Dividends" stackId="payout" fill={S4} maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                  <Line type="monotone" dataKey="fcf" name="Free CF" stroke={S3} strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Tooltip {...tooltipStyle} formatter={(v) => fmtB(Number(v))} />
                </ComposedChart>
              </ResponsiveContainer>
              <Legend items={[{ label: "Buybacks", color: S2 }, { label: "Dividends", color: S4 }, { label: "Free CF", color: S3 }]} />
              {overpaidYears.length > 0 && (
                <Caption>⚠ Payout exceeded free cash flow in {overpaidYears.join(", ")} — funded from cash reserves or debt.</Caption>
              )}
            </div>
          </div>
        </ChartSection>
      )}

      {/* 6 — Valuation vs own history */}
      {ratios.length > 1 && (
        <ChartSection title="Valuation vs own history">
          <div className="grid gap-4 sm:grid-cols-3">
            {(
              [
                { key: "priceToEarningsRatio", label: "P/E" },
                { key: "priceToSalesRatio", label: "P/S" },
                { key: "priceToBookRatio", label: "P/B" },
              ] as const
            ).map((m) => {
              const series = ratios.map((r) => ({ year: yearOf(r.date), value: r[m.key] }));
              const values = series.map((s) => s.value).filter((v): v is number => v != null);
              const min = Math.min(...values);
              const max = Math.max(...values);
              const avg = values.reduce((a, b) => a + b, 0) / (values.length || 1);
              return (
                <div key={m.key}>
                  <p className="mb-1 text-xs text-zinc-500">{m.label}</p>
                  <ResponsiveContainer width="100%" height={140}>
                    <ComposedChart data={series}>
                      <CartesianGrid stroke={CHART_DEFAULTS.gridColor} vertical={false} />
                      <XAxis dataKey="year" tick={axisTick} tickLine={false} axisLine={false} />
                      <YAxis tick={axisTick} tickLine={false} axisLine={false} width={36} domain={["auto", "auto"]} />
                      {values.length > 1 && (
                        <ReferenceArea y1={min} y2={max} fill={S1} fillOpacity={0.08} stroke="none" />
                      )}
                      {values.length > 1 && (
                        <ReferenceLine y={avg} stroke={CHART_DEFAULTS.textColor} strokeDasharray="3 3" />
                      )}
                      <Line type="monotone" dataKey="value" name={m.label} stroke={S1} strokeWidth={2} dot={false} isAnimationActive={false} />
                      <Tooltip {...tooltipStyle} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              );
            })}
          </div>
          <Caption>
            Shaded band = this ticker's own min–max over the loaded history; dashed line = its average. "Expensive
            relative to its own past," not an absolute threshold. Band tightens as more history backfills.
          </Caption>
        </ChartSection>
      )}

      {/* 7 — Working capital cycle */}
      {efficiency.length > 0 && (
        <ChartSection title="Working capital cycle">
          <div className="grid gap-4 sm:grid-cols-[2fr_1fr]">
            <div>
              <ResponsiveContainer width="100%" height={160}>
                <ComposedChart data={efficiency}>
                  <CartesianGrid stroke={CHART_DEFAULTS.gridColor} vertical={false} />
                  <XAxis dataKey="year" tick={axisTick} tickLine={false} axisLine={false} />
                  <YAxis tick={axisTick} tickLine={false} axisLine={false} width={36} />
                  <Bar dataKey="dso" name="Days sales out." fill={S1} maxBarSize={16} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                  <Bar dataKey="dio" name="Days inventory" fill={S2} maxBarSize={16} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                  <Bar dataKey="dpo" name="Days payables" fill={S3} maxBarSize={16} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                  <Tooltip {...tooltipStyle} formatter={(v) => `${Number(v).toFixed(0)} days`} />
                </ComposedChart>
              </ResponsiveContainer>
              <Legend items={[{ label: "DSO", color: S1 }, { label: "DIO", color: S2 }, { label: "DPO", color: S3 }]} />
            </div>
            <div className="flex flex-col justify-center rounded-lg bg-zinc-950/60 p-4">
              <p className="text-xs text-zinc-500">Cash conversion cycle</p>
              <p className={`text-3xl font-semibold ${ccc != null && ccc < 0 ? "text-emerald-400" : "text-zinc-200"}`}>
                {ccc == null ? "—" : `${ccc.toFixed(0)} days`}
              </p>
              {ccc != null && ccc < 0 && (
                <p className="mt-1 text-[11px] leading-snug text-zinc-500">
                  Negative — suppliers effectively finance operations. Rare and genuinely impressive.
                </p>
              )}
            </div>
          </div>
        </ChartSection>
      )}

      {/* Key ratio cards */}
      {(latestRatios || latestKM) && (
        <ChartSection title="Key ratios">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            <MetricCard
              metricKey="priceToEarningsRatio"
              label="P/E"
              value={latestRatios?.priceToEarningsRatio}
              trend={trendOf(latestRatios?.priceToEarningsRatio, prevRatios?.priceToEarningsRatio)}
            />
            <MetricCard
              metricKey="enterpriseValueMultiple"
              label="EV/EBITDA"
              value={latestRatios?.enterpriseValueMultiple}
              trend={trendOf(latestRatios?.enterpriseValueMultiple, prevRatios?.enterpriseValueMultiple)}
            />
            <MetricCard
              metricKey="freeCashFlowYield"
              label="FCF yield"
              value={latestKM?.freeCashFlowYield}
              trend={trendOf(latestKM?.freeCashFlowYield, prevKM?.freeCashFlowYield)}
            />
            <MetricCard
              metricKey="debtToEquityRatio"
              label="Debt/equity"
              value={latestRatios?.debtToEquityRatio}
              trend={trendOf(latestRatios?.debtToEquityRatio, prevRatios?.debtToEquityRatio)}
            />
            <MetricCard
              metricKey="grossProfitMargin"
              label="Gross margin"
              value={latestRatios?.grossProfitMargin}
              trend={trendOf(latestRatios?.grossProfitMargin, prevRatios?.grossProfitMargin)}
            />
            <MetricCard
              metricKey="returnOnEquity"
              label="ROE"
              value={latestKM?.returnOnEquity}
              trend={trendOf(latestKM?.returnOnEquity, prevKM?.returnOnEquity)}
              caption={roeElevated ? "Elevated by buybacks shrinking equity" : undefined}
            />
            <MetricCard
              metricKey="returnOnInvestedCapital"
              label="ROIC"
              value={latestKM?.returnOnInvestedCapital}
              trend={trendOf(latestKM?.returnOnInvestedCapital, prevKM?.returnOnInvestedCapital)}
            />
          </div>
          <Caption>
            Color = where the value sits in its typical market range (ice blue low → red high), independent of
            whether high is good for that ratio — the label carries the meaning.
          </Caption>
        </ChartSection>
      )}
    </div>
  );
}

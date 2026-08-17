// Spec: specs/021-stock-page-redesign US7 (FR-013, FR-014)
// 13F is not entitled on the current data plan (verified 402), so the net
// bought/sold read is built from 13D/G beneficial-ownership filings — the 5%+
// holders that actually move a name — with the stale cached 13F top-10 tallies
// as a secondary, clearly-labeled signal.
import {
  Bar,
  ComposedChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { BeneficialFiling, InstitutionalReport } from "../../api/types";
import { CHART_DEFAULTS } from "../../lib/constants";
import { formatDate } from "../../lib/time";

const DIRECTION_STYLES: Record<string, { label: string; className: string }> = {
  accumulating: {
    label: "5%+ holders accumulating",
    className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  },
  distributing: {
    label: "5%+ holders distributing",
    className: "border-red-500/30 bg-red-500/10 text-red-400",
  },
  mixed: {
    label: "5%+ holders mixed",
    className: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  },
};

const SNAPSHOT_STYLES: Record<string, string> = {
  buying: "text-emerald-400",
  selling: "text-red-400",
  mixed: "text-amber-400",
};

/** Latest disclosed stake per filer — the "who owns what" bar chart. */
function latestByFiler(filings: BeneficialFiling[]): BeneficialFiling[] {
  const seen = new Map<string, BeneficialFiling>();
  for (const f of filings) {
    const prev = seen.get(f.filer);
    if (!prev || f.filing_date > prev.filing_date) seen.set(f.filer, f);
  }
  return [...seen.values()].sort((a, b) => b.pct_of_class - a.pct_of_class).slice(0, 10);
}

export default function InstitutionalFlowVisuals({
  institutional,
}: {
  institutional: InstitutionalReport;
}) {
  const filings = institutional.beneficial_filings ?? [];
  const direction = institutional.beneficial_direction ?? null;
  const summary = institutional.institutional_summary;
  const up = summary?.top10_increasing ?? 0;
  const down = summary?.top10_decreasing ?? 0;
  const snapshotDirection = !up && !down ? null : up > down ? "buying" : down > up ? "selling" : "mixed";

  if (!filings.length && !snapshotDirection) {
    return (
      <p className="py-6 text-center text-sm text-zinc-600">
        No institutional ownership filings available for this ticker.
      </p>
    );
  }

  const chartData = latestByFiler(filings).map((f) => ({
    filer: f.filer.length > 28 ? `${f.filer.slice(0, 27)}…` : f.filer,
    pct: f.pct_of_class,
  }));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {direction && DIRECTION_STYLES[direction] && (
          <span
            className={`rounded-full border px-2.5 py-0.5 text-xs ${DIRECTION_STYLES[direction].className}`}
          >
            {DIRECTION_STYLES[direction].label}
          </span>
        )}
        {snapshotDirection && (
          <span className="text-xs text-zinc-500">
            cached 13F top-10:{" "}
            <span className={SNAPSHOT_STYLES[snapshotDirection]}>{snapshotDirection}</span> ({up} up /{" "}
            {down} down)
            {summary?.as_of && ` — as of ${formatDate(summary.as_of) || summary.as_of}`}
          </span>
        )}
      </div>

      {chartData.length > 0 && (
        <div>
          <p className="mb-1 text-[10px] uppercase tracking-wide text-zinc-600">
            largest disclosed stakes (% of class)
          </p>
          <ResponsiveContainer width="100%" height={Math.max(120, chartData.length * 26)}>
            <ComposedChart data={chartData} layout="vertical" margin={{ left: 8, right: 16 }}>
              <XAxis
                type="number"
                tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) => `${v}%`}
              />
              <YAxis
                type="category"
                dataKey="filer"
                width={170}
                tick={{ fill: CHART_DEFAULTS.textColor, fontSize: 10 }}
                tickLine={false}
                axisLine={false}
              />
              <Bar dataKey="pct" fill={CHART_DEFAULTS.accentColor} fillOpacity={0.7} isAnimationActive={false} />
              <Tooltip
                cursor={{ fill: "#ffffff08" }}
                contentStyle={{ backgroundColor: "#09090b", border: "1px solid #27272a", borderRadius: 8, fontSize: 11 }}
                labelStyle={{ color: "#a1a1aa" }}
                formatter={(v) => [`${Number(v).toFixed(2)}%`, "of class"]}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {filings.length > 0 && (
        <div>
          <p className="mb-2 text-[10px] uppercase tracking-wide text-zinc-600">
            recent 5%+ / activist filings
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-zinc-500">
                <tr>
                  <th className="pb-2 pr-4">Filer</th>
                  <th className="pb-2 pr-4">Type</th>
                  <th className="pb-2 pr-4 text-right">Shares</th>
                  <th className="pb-2 pr-4 text-right">% class</th>
                  <th className="pb-2">Filed</th>
                </tr>
              </thead>
              <tbody className="text-zinc-300">
                {filings.slice(0, 10).map((f, i) => (
                  <tr key={`${f.filer}-${f.filing_date}-${i}`} className="border-t border-zinc-800/60">
                    <td className="py-1.5 pr-4">
                      {f.url ? (
                        <a href={f.url} target="_blank" rel="noreferrer" className="hover:text-sky-400">
                          {f.filer}
                        </a>
                      ) : (
                        f.filer
                      )}
                    </td>
                    <td className="py-1.5 pr-4 text-zinc-500">{f.filer_type}</td>
                    <td className="py-1.5 pr-4 text-right font-mono">{f.shares.toLocaleString()}</td>
                    <td className="py-1.5 pr-4 text-right font-mono">{f.pct_of_class.toFixed(2)}%</td>
                    <td className="py-1.5 text-zinc-500">{f.filing_date}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

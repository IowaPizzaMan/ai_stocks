// Spec: specs/029-company-profile-tweaks/contracts/company-profile-api.md (US7)
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { EmployeeCountRecord } from "../../api/types";
import { useEmployeeCounts } from "../../hooks/useCompanyProfile";
import { CHART_DEFAULTS } from "../../lib/constants";

const tooltipStyle = {
  contentStyle: { backgroundColor: "#09090b", border: "1px solid #27272a", borderRadius: 8, fontSize: 12 },
  labelStyle: { color: "#a1a1aa" },
};

const axisTick = { fill: CHART_DEFAULTS.textColor, fontSize: 11 };

function formatCount(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${(v / 1e3).toFixed(0)}k`;
  return `${v}`;
}

function TooltipContent({ active, payload }: { active?: boolean; payload?: { payload: EmployeeCountRecord }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-xs">
      <div className="text-zinc-400">{r.period_of_report}</div>
      <div className="text-zinc-100">{r.employee_count?.toLocaleString() ?? "—"} employees</div>
      <div className="text-zinc-500">{r.form_type}</div>
    </div>
  );
}

export default function EmployeeCountChart({ ticker }: { ticker: string }) {
  const { data, isLoading } = useEmployeeCounts(ticker);
  const records = data?.records ?? [];

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">
        Employee Count
      </h2>

      {isLoading && <p className="text-sm text-zinc-600">loading employee history…</p>}

      {!isLoading && records.length === 0 && (
        <p className="text-sm text-zinc-500">No reported employee history.</p>
      )}

      {!isLoading && records.length > 0 && (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={records} margin={{ top: 6, right: 16, bottom: 0, left: 0 }}>
            <XAxis dataKey="period_of_report" tick={axisTick} tickLine={false} axisLine={false} />
            <YAxis
              tickFormatter={formatCount}
              tick={axisTick}
              tickLine={false}
              axisLine={false}
              width={48}
              domain={["auto", "auto"]}
            />
            <Tooltip content={<TooltipContent />} {...tooltipStyle} />
            <Line
              type="monotone"
              dataKey="employee_count"
              stroke="#0284c7"
              strokeWidth={2}
              dot={records.length === 1 ? { r: 4 } : { r: 2 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </section>
  );
}

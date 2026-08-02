// Spec: specs/component-specs/frontend/components/earnings/EarningsCandidateCard.md
// Modal detail view: score breakdown bars + post-earnings move history chart.
import { Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import type { EarningsCandidate } from "../../api/types";
import { useEarningsHistory } from "../../hooks/useEarningsScan";
import { scoreColor } from "./EarningsCalendarTable";

interface EarningsCandidateCardProps {
  candidate: EarningsCandidate;
  queued: boolean;
  onAnalyze: (ticker: string) => void;
  onClose: () => void;
}

function ScoreBar({ label, detail, pts, max }: {
  label: string;
  detail: string;
  pts: number;
  max: number;
}) {
  const pct = Math.min((pts / max) * 100, 100);
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="w-28 text-zinc-400">{label}</span>
      <span className="w-16 text-zinc-300">{detail}</span>
      <div className="h-1.5 flex-1 rounded-full bg-zinc-800">
        <div className="h-full rounded-full bg-indigo-500" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-16 text-right text-xs text-zinc-400">
        {pts}/{max} pts
      </span>
    </div>
  );
}

const REPORT_TIME_LABEL = {
  bmo: "before market open",
  amc: "after market close",
  unknown: "",
} as const;

export default function EarningsCandidateCard({
  candidate: c,
  queued,
  onAnalyze,
  onClose,
}: EarningsCandidateCardProps) {
  const { data: history, isLoading: historyLoading } = useEarningsHistory(c.ticker);
  const b = c.score_breakdown;
  const beats = Math.round(c.beat_rate * c.history_quarters);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
      role="dialog"
      aria-label={`${c.ticker} earnings candidate details`}
    >
      <div
        className="w-full max-w-lg rounded-xl border border-zinc-700 bg-zinc-900 p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-1 flex items-start justify-between">
          <div>
            <span className="text-lg font-semibold">{c.ticker}</span>
            <span className="ml-2 text-sm text-zinc-400">{c.company}</span>
          </div>
          <div className="flex items-center gap-3">
            <span className={`text-2xl font-semibold ${scoreColor(c.score)}`}>{c.score}</span>
            <button onClick={onClose} aria-label="Close" className="text-zinc-500 hover:text-white">
              ✕
            </button>
          </div>
        </div>
        <p className="mb-1 text-sm text-zinc-400">
          Reports {c.report_date} {REPORT_TIME_LABEL[c.report_time]}
        </p>
        <p className="mb-4 text-sm text-zinc-300">{c.one_line_thesis}</p>

        <h3 className="mb-2 text-xs font-medium uppercase text-zinc-500">Score breakdown</h3>
        <div className="mb-5 space-y-2">
          <ScoreBar label="Avg move" detail={`±${c.avg_abs_move_pct.toFixed(1)}%`}
            pts={b.move_pts} max={25} />
          <ScoreBar label="Beat rate"
            detail={c.history_quarters > 0 ? `${beats}/${c.history_quarters}` : "—"}
            pts={b.beat_pts} max={20} />
          <ScoreBar label="EPS revision" detail={c.eps_revision} pts={b.revision_pts} max={20} />
          <ScoreBar label="Insider" detail={c.insider_signal} pts={b.insider_pts} max={20} />
          <ScoreBar label="Accumulation" detail={`${c.accumulation_score}/5`}
            pts={b.accumulation_pts} max={15} />
        </div>

        <h3 className="mb-2 text-xs font-medium uppercase text-zinc-500">
          Post-earnings moves (last {history?.num_quarters ?? "…"} quarters)
        </h3>
        <div className="mb-5 h-24">
          {historyLoading && <div className="h-full animate-pulse rounded bg-zinc-800" />}
          {history && history.quarters.length > 0 && (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={[...history.quarters].reverse()}>
                <XAxis dataKey="period" hide />
                <Tooltip
                  cursor={{ fill: "rgba(255,255,255,0.05)" }}
                  contentStyle={{ background: "#18181b", border: "1px solid #3f3f46" }}
                  formatter={(value) => `${value}%`}
                />
                <ReferenceLine y={0} stroke="#52525b" />
                <Bar dataKey="move_pct">
                  {[...history.quarters].reverse().map((q, i) => (
                    <Cell key={i} fill={q.move_pct >= 0 ? "#22c55e" : "#ef4444"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
          {history && history.quarters.length === 0 && (
            <p className="text-sm text-zinc-500">No history available.</p>
          )}
        </div>

        {queued ? (
          <span className="block rounded-lg bg-zinc-800 py-2 text-center text-sm text-green-400">
            Queued for analysis
          </span>
        ) : (
          <button
            onClick={() => onAnalyze(c.ticker)}
            className="w-full rounded-lg bg-indigo-600 py-2 text-sm font-medium text-white hover:bg-indigo-500"
          >
            Analyze This Stock ▶
          </button>
        )}
      </div>
    </div>
  );
}

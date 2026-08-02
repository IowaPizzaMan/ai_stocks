// Spec: specs/component-specs/frontend/components/earnings/EarningsCalendarTable.md
// Ranked scan results. Clicking a row (or Analyze) enqueues the ticker
// directly into work_queue — no chat step. "Details" opens the score card.
import { useState } from "react";
import type { EarningsCandidate } from "../../api/types";

interface EarningsCalendarTableProps {
  candidates: EarningsCandidate[];
  isLoading: boolean;
  queuedTickers: Set<string>;
  onAnalyzeTicker: (ticker: string) => void;
  onShowDetails: (candidate: EarningsCandidate) => void;
}

type SortKey = "score" | "report_date" | "avg_abs_move_pct" | "beat_rate" | "market_cap";

export const scoreColor = (score: number) =>
  score >= 70 ? "text-green-400" : score >= 40 ? "text-amber-400" : "text-zinc-400";

const REVISION_DISPLAY = {
  up: { label: "↑ Up", cls: "text-green-400" },
  flat: { label: "→ Flat", cls: "text-zinc-400" },
  down: { label: "↓ Down", cls: "text-red-400" },
} as const;

const INSIDER_DISPLAY = {
  cluster: { label: "● Cluster", cls: "text-sky-400" },
  single: { label: "● Single", cls: "text-amber-400" },
  none: { label: "—", cls: "text-zinc-600" },
} as const;

function AccumulationDots({ score }: { score: number }) {
  return (
    <span aria-label={`accumulation ${score}/5`} className="tracking-tighter">
      {Array.from({ length: 5 }).map((_, i) => (
        <span key={i} className={i < score ? "text-indigo-400" : "text-zinc-700"}>
          •
        </span>
      ))}
    </span>
  );
}

const HEADERS: { key: SortKey | null; label: string }[] = [
  { key: null, label: "#" },
  { key: null, label: "Ticker" },
  { key: "report_date", label: "Reports" },
  { key: "score", label: "Score" },
  { key: "avg_abs_move_pct", label: "Avg Move" },
  { key: "beat_rate", label: "Beat Rate" },
  { key: null, label: "EPS Rev." },
  { key: null, label: "Insider" },
  { key: null, label: "Accu." },
  { key: null, label: "" },
];

export default function EarningsCalendarTable({
  candidates,
  isLoading,
  queuedTickers,
  onAnalyzeTicker,
  onShowDetails,
}: EarningsCalendarTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir(sortDir === "desc" ? "asc" : "desc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const sorted = [...candidates].sort((a, b) => {
    const av = a[sortKey];
    const bv = b[sortKey];
    const cmp =
      typeof av === "string"
        ? av.localeCompare(bv as string)
        : (av as number) - (bv as number);
    return sortDir === "desc" ? -cmp : cmp;
  });

  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 bg-zinc-900 text-xs uppercase text-zinc-500">
          <tr>
            {HEADERS.map(({ key, label }, i) => (
              <th key={i} className="px-3 py-2.5 font-medium">
                {key ? (
                  <button onClick={() => toggleSort(key)} className="hover:text-zinc-300">
                    {label}
                    {sortKey === key && (sortDir === "desc" ? " ↓" : " ↑")}
                  </button>
                ) : (
                  label
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {isLoading &&
            Array.from({ length: 5 }).map((_, i) => (
              <tr key={i} className="animate-pulse border-t border-zinc-800">
                {Array.from({ length: HEADERS.length }).map((_, j) => (
                  <td key={j} className="px-3 py-3">
                    <div className="h-4 w-full max-w-16 rounded bg-zinc-800" />
                  </td>
                ))}
              </tr>
            ))}

          {!isLoading &&
            sorted.map((c, rank) => {
              const queued = queuedTickers.has(c.ticker);
              const beats = Math.round(c.beat_rate * c.history_quarters);
              return (
                <tr
                  key={c.ticker}
                  onClick={() => !queued && onAnalyzeTicker(c.ticker)}
                  title={c.one_line_thesis}
                  className={`cursor-pointer border-t border-zinc-800 hover:bg-zinc-800/60 ${
                    rank % 2 === 1 ? "bg-zinc-800/20" : ""
                  }`}
                >
                  <td className="px-3 py-2.5 text-zinc-500">{rank + 1}</td>
                  <td className="px-3 py-2.5">
                    <span className="font-semibold">{c.ticker}</span>
                    <span className="block max-w-40 truncate text-xs text-zinc-500">
                      {c.company}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    {c.report_date}
                    {c.report_time !== "unknown" && (
                      <span className="ml-1.5 rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] uppercase text-zinc-400">
                        {c.report_time}
                      </span>
                    )}
                  </td>
                  <td className={`px-3 py-2.5 text-lg font-semibold ${scoreColor(c.score)}`}>
                    {c.score}
                  </td>
                  <td className="px-3 py-2.5">±{c.avg_abs_move_pct.toFixed(1)}%</td>
                  <td className="px-3 py-2.5">
                    {c.history_quarters > 0 ? `${beats}/${c.history_quarters}` : "—"}
                  </td>
                  <td className={`px-3 py-2.5 ${REVISION_DISPLAY[c.eps_revision].cls}`}>
                    {REVISION_DISPLAY[c.eps_revision].label}
                  </td>
                  <td className={`px-3 py-2.5 ${INSIDER_DISPLAY[c.insider_signal].cls}`}>
                    {INSIDER_DISPLAY[c.insider_signal].label}
                  </td>
                  <td className="px-3 py-2.5">
                    <AccumulationDots score={c.accumulation_score} />
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onShowDetails(c);
                      }}
                      className="mr-2 text-xs text-zinc-400 hover:text-white"
                    >
                      Details
                    </button>
                    {queued ? (
                      <span className="rounded-full bg-zinc-800 px-2 py-1 text-xs text-green-400">
                        Queued
                      </span>
                    ) : (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onAnalyzeTicker(c.ticker);
                        }}
                        className="rounded bg-indigo-600/20 px-2 py-1 text-xs text-indigo-300 hover:bg-indigo-600/40"
                      >
                        Analyze ▶
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
        </tbody>
      </table>
    </div>
  );
}

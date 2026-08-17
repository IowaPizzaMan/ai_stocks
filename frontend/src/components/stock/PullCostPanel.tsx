// Spec: specs/024-delta-data-pulls US1 (FR-001..FR-004, SC-006)
// Where a pull's time actually went. Diagnostic, so it sits collapsed by
// default — but the three most expensive stages stay readable without opening
// it, which is the whole point of SC-006.
//
// Stages arrive already sorted most-expensive-first from the API
// (contracts/queue-pull-mode.md); this component never re-ranks them.
import { useState } from "react";
import type { Pull, PullStage } from "../../api/types";

const TOP_N = 3;

function formatMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatBytes(bytes: number): string {
  if (bytes <= 0) return "—";
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

const RETRIEVAL_STYLES: Record<string, string> = {
  incremental: "bg-emerald-500/10 text-emerald-400",
  full: "bg-amber-500/10 text-amber-400",
  stored: "bg-zinc-700/40 text-zinc-400",
};

const OUTCOME_STYLES: Record<string, string> = {
  degraded: "bg-amber-500/10 text-amber-400",
  failed: "bg-rose-500/10 text-rose-400",
  skipped: "bg-zinc-700/40 text-zinc-400",
};

function StageRow({ stage, maxMs }: { stage: PullStage; maxMs: number }) {
  const share = maxMs > 0 ? Math.max(2, (stage.elapsed_ms / maxMs) * 100) : 0;
  return (
    <li data-stage-name={stage.name} className="flex items-center gap-3 py-1 text-xs">
      <span className="w-24 shrink-0 truncate text-zinc-300">{stage.name}</span>
      <span className="h-1.5 w-24 shrink-0 overflow-hidden rounded-full bg-zinc-800">
        <span className="block h-full rounded-full bg-sky-500/70" style={{ width: `${share}%` }} />
      </span>
      <span className="w-14 shrink-0 text-right tabular-nums text-zinc-400">
        {formatMs(stage.elapsed_ms)}
      </span>
      <span className="w-20 shrink-0 text-right tabular-nums text-zinc-500">
        {stage.requests > 0 ? `${stage.requests} req` : "0 req"}
      </span>
      <span className="w-14 shrink-0 text-right tabular-nums text-zinc-500">
        {formatBytes(stage.bytes)}
      </span>
      {stage.retrieval && (
        <span
          className={`rounded px-1.5 py-0.5 ${RETRIEVAL_STYLES[stage.retrieval] ?? RETRIEVAL_STYLES.stored}`}
        >
          {stage.retrieval}
        </span>
      )}
      {stage.outcome && OUTCOME_STYLES[stage.outcome] && (
        <span className={`rounded px-1.5 py-0.5 ${OUTCOME_STYLES[stage.outcome]}`}>
          {stage.outcome}
        </span>
      )}
    </li>
  );
}

export default function PullCostPanel({ pull }: { pull: Pull | null }) {
  const [expanded, setExpanded] = useState(false);

  if (!pull) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 px-4 py-3 text-xs text-zinc-500">
        No pull recorded for this ticker yet.
      </div>
    );
  }

  const stages = pull.stages ?? [];
  const shown = expanded ? stages : stages.slice(0, TOP_N);
  const maxMs = stages.length > 0 ? stages[0].elapsed_ms : 0;
  const modeLabel = pull.mode === "full" ? "full refresh" : "delta";

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/40">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-2 text-left text-xs text-zinc-400 transition-colors hover:text-zinc-200"
      >
        <span className="flex items-center gap-2">
          <span className="font-medium text-zinc-300">Pull cost</span>
          <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-zinc-400">{modeLabel}</span>
          {pull.outcome !== "done" && (
            <span
              className={`rounded px-1.5 py-0.5 ${OUTCOME_STYLES[pull.outcome] ?? "bg-zinc-800 text-zinc-400"}`}
            >
              {pull.outcome}
            </span>
          )}
          <span className="tabular-nums text-zinc-500">{formatMs(pull.total_ms)} total</span>
        </span>
        <span className="text-zinc-600">{expanded ? "▾" : "▸"}</span>
      </button>

      {stages.length === 0 ? (
        <p className="px-4 pb-3 text-xs text-zinc-500">No stage detail was recorded for this pull.</p>
      ) : (
        <ul className="px-4 pb-2">
          {shown.map((stage) => (
            <StageRow key={stage.name} stage={stage} maxMs={maxMs} />
          ))}
        </ul>
      )}

      {expanded && stages.length > 0 && (
        // FR-004 — time the stage breakdown can't explain is itself a finding,
        // so it is shown rather than quietly folded into the total.
        <p className="border-t border-zinc-800 px-4 py-2 text-xs text-zinc-500">
          {formatMs(pull.accounted_ms)} across {stages.length} stages ·{" "}
          <span className="text-zinc-400">{formatMs(pull.unaccounted_ms)} unaccounted</span>
        </p>
      )}
    </div>
  );
}

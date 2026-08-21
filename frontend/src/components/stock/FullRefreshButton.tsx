// Spec: specs/024-delta-data-pulls US5 (FR-023, FR-024, FR-028, FR-029)
// The operator's escape hatch: rebuild every delta-maintained dataset for this
// ticker from scratch and re-run the analysis on the result.
//
// Delta pulls are the default and nothing re-baselines on a schedule, so this
// is the ONLY way to correct stored data that has gone wrong — most notably a
// split, which silently invalidates years of stored bars with no warning
// anywhere (spec Assumptions: silent drift is an accepted risk).
//
// It confirms before firing: it replaces stored data and spends real API
// budget. Same inline-popover pattern as feed/RemoveTickerConfirm.
import { useEffect, useRef, useState } from "react";

export default function FullRefreshButton({
  ticker,
  onRefresh,
  pending = false,
  busy = false,
  hasData = true,
}: {
  ticker: string;
  onRefresh: () => void;
  /** The refresh request is in flight. */
  pending?: boolean;
  /** A pull for this ticker is already running — too late to upgrade it. */
  busy?: boolean;
  /** Whether anything is stored yet. Never disables the control (FR-029). */
  hasData?: boolean;
}) {
  const [confirming, setConfirming] = useState(false);
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (confirming) confirmRef.current?.focus();
  }, [confirming]);

  if (busy) {
    // research D8 — a running job can't be upgraded to a full refresh. Say so
    // rather than letting the operator believe one was queued.
    return (
      <span className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-400">
        pull already running — retry the refresh when it lands
      </span>
    );
  }

  if (pending) {
    return (
      <span className="flex items-center gap-2 rounded-lg bg-amber-500/10 px-3 py-1.5 text-sm text-amber-400">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-400" />
        refreshing…
      </span>
    );
  }

  if (confirming) {
    return (
      <div
        role="dialog"
        aria-label={`Full refresh ${ticker}`}
        onKeyDown={(e) => {
          if (e.key === "Escape") setConfirming(false);
        }}
        className="w-64 rounded-lg border border-zinc-700 bg-zinc-900 p-3 text-left shadow-xl"
      >
        <p className="mb-3 text-xs leading-snug text-zinc-300">
          Re-download <span className="font-semibold text-white">{ticker}</span>'s price
          history, news and filings from scratch, then re-run the analysis?
          {!hasData && " Nothing is stored yet, so this behaves as a first pull."}
        </p>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            aria-label={`Cancel full refresh ${ticker}`}
            onClick={() => setConfirming(false)}
            className="rounded px-2 py-1 text-xs text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
          >
            Cancel
          </button>
          <button
            ref={confirmRef}
            type="button"
            aria-label={`Confirm full refresh ${ticker}`}
            onClick={() => {
              setConfirming(false);
              onRefresh();
            }}
            className="rounded bg-amber-600 px-2 py-1 text-xs font-medium text-white hover:bg-amber-500"
          >
            Full Refresh
          </button>
        </div>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => setConfirming(true)}
      title="Re-download this stock's data from scratch and re-run the analysis"
      className="rounded-lg border border-zinc-700 px-3 py-1.5 text-sm text-zinc-300 transition-colors hover:border-amber-500/50 hover:text-amber-400"
    >
      Full Refresh ⟳
    </button>
  );
}

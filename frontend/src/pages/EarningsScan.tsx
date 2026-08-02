// Spec: specs/component-specs/frontend/pages/EarningsScan.md
// Single-pane scan view: run a scan, get a ranked table, click a row to
// enqueue the full crew. Not conversational.
import { useEffect, useState } from "react";
import type { EarningsCandidate } from "../api/types";
import EarningsCalendarTable from "../components/earnings/EarningsCalendarTable";
import EarningsCandidateCard from "../components/earnings/EarningsCandidateCard";
import ScanControls, { type ScanConfig } from "../components/earnings/ScanControls";
import { useAnalyzeTickers, useEarningsScan } from "../hooks/useEarningsScan";

export default function EarningsScan() {
  const { startScan, scan, isScanning, status, startError } = useEarningsScan();
  const analyze = useAnalyzeTickers();
  const [queuedTickers, setQueuedTickers] = useState<Set<string>>(new Set());
  const [minCapBn, setMinCapBn] = useState(0.5);
  const [daysAhead, setDaysAhead] = useState(7);
  const [detail, setDetail] = useState<EarningsCandidate | null>(null);

  useEffect(() => {
    document.title = "StockAI — Earnings Scanner";
  }, []);

  const onScan = (config: ScanConfig) => {
    setDaysAhead(config.days_ahead);
    setMinCapBn(config.min_market_cap_bn);
    startScan(config.days_ahead);
  };

  const analyzeTicker = (ticker: string) => {
    analyze.mutate([ticker]);
    setQueuedTickers((prev) => new Set(prev).add(ticker));
  };

  // backend screens at $500M; the dropdown narrows the displayed set further
  const candidates = (scan?.candidates ?? []).filter(
    (c) => c.market_cap >= minCapBn * 1e9,
  );

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <h1 className="text-xl font-semibold">Earnings Scanner</h1>

      <ScanControls onScan={onScan} onMinCapChange={setMinCapBn} isScanning={isScanning} />

      {status === "idle" && (
        <div className="py-16 text-center text-zinc-500">
          <p className="mb-1 text-lg text-zinc-400">No scan yet</p>
          <p className="text-sm">
            Scan the calendar to score every company reporting in the coming days —
            big historical movers, rising estimates, insider buying, accumulation.
          </p>
        </div>
      )}

      {isScanning && (
        <p className="text-sm text-zinc-400">
          Scanning companies reporting in the next {daysAhead} days… this enriches the
          top candidates with earnings history, insider activity, and volume data
          (takes a couple of minutes).
        </p>
      )}

      {status === "failed" && (
        <p className="py-4 text-center text-sm text-red-400">
          Scan failed{scan?.error ? `: ${scan.error}` : ""} — is the agent-runner up?
        </p>
      )}

      {startError && (
        <p className="py-4 text-center text-sm text-red-400">
          Couldn't start the scan — is the backend running?
        </p>
      )}

      {status === "complete" && (
        <p className="text-sm text-zinc-500">
          Scored {candidates.length}
          {scan?.scored_count !== candidates.length ? ` of ${scan?.scored_count}` : ""} candidates
          (screened {scan?.total_screened} companies ≥ $500M reporting in the next{" "}
          {scan?.days_ahead} days).
        </p>
      )}

      {(isScanning || (status === "complete" && candidates.length > 0)) && (
        <EarningsCalendarTable
          candidates={candidates}
          isLoading={isScanning}
          queuedTickers={queuedTickers}
          onAnalyzeTicker={analyzeTicker}
          onShowDetails={setDetail}
        />
      )}

      {status === "complete" && candidates.length === 0 && (
        <p className="py-8 text-center text-sm text-zinc-500">
          No candidates above the selected market-cap floor — lower it or widen the window.
        </p>
      )}

      {detail && (
        <EarningsCandidateCard
          candidate={detail}
          queued={queuedTickers.has(detail.ticker)}
          onAnalyze={(t) => {
            analyzeTicker(t);
          }}
          onClose={() => setDetail(null)}
        />
      )}
    </div>
  );
}

// Spec: specs/component-specs/frontend/pages/EarningsScan.md
// Single-pane scan view: the upcoming calendar is always browsable with a
// per-row Queue button (the backend calendar endpoint is read-only); running
// a scan scores the top candidates into a ranked table. Not conversational.
import { useEffect, useState } from "react";
import type { EarningsCandidate } from "../api/types";
import EarningsCalendarTable from "../components/earnings/EarningsCalendarTable";
import EarningsCandidateCard from "../components/earnings/EarningsCandidateCard";
import ScanControls, { type ScanConfig } from "../components/earnings/ScanControls";
import UpcomingEarningsTable from "../components/earnings/UpcomingEarningsTable";
import {
  useAnalyzeTickers,
  useEarningsCalendar,
  useEarningsScan,
} from "../hooks/useEarningsScan";

export default function EarningsScan() {
  const { startScan, scan, isScanning, status, startError } = useEarningsScan();
  const analyze = useAnalyzeTickers();
  const [queuedTickers, setQueuedTickers] = useState<Set<string>>(new Set());
  const [minCapBn, setMinCapBn] = useState(0.5);
  const [daysAhead, setDaysAhead] = useState(7);
  const [detail, setDetail] = useState<EarningsCandidate | null>(null);

  const calendar = useEarningsCalendar(daysAhead);

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
  const calendarEntries = (calendar.data ?? []).filter(
    (e) => e.market_cap >= minCapBn * 1e9,
  );

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <h1 className="text-xl font-semibold">Earnings Scanner</h1>

      <ScanControls
        onScan={onScan}
        onMinCapChange={setMinCapBn}
        onDaysChange={setDaysAhead}
        isScanning={isScanning}
      />

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

      <section className="space-y-2">
        <h2 className="text-sm font-medium uppercase text-zinc-500">
          Upcoming earnings (next {daysAhead} days, ≥ $500M)
        </h2>
        {calendar.isError && (
          <p className="py-4 text-center text-sm text-red-400">
            Couldn't load the calendar — is the backend running?
          </p>
        )}
        <UpcomingEarningsTable
          entries={calendarEntries}
          isLoading={calendar.isLoading}
          queuedTickers={queuedTickers}
          onQueueTicker={analyzeTicker}
        />
      </section>

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

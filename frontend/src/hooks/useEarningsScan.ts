// React Query hooks for /earnings endpoints: trigger a scan, poll it to
// completion, enqueue selected tickers, and lazy-load a ticker's move history.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import type { EarningsCalendarEntry, EarningsHistory, EarningsScanDoc } from "../api/types";

/** Upcoming pre-screened calendar (read-only on the backend — queuing a
 * ticker is an explicit per-row action via useAnalyzeTickers). */
export function useEarningsCalendar(days: number) {
  return useQuery({
    queryKey: ["earnings-calendar", days],
    queryFn: async () => {
      const { data } = await api.get<EarningsCalendarEntry[]>(`/earnings/calendar?days=${days}`);
      return data;
    },
    staleTime: 60 * 60 * 1000, // backend caches 4h; don't hammer on tab focus
  });
}

/** Scan lifecycle: POST /earnings/scan returns a scan_id; the agent-runner
 * picks the job up from Mongo, so we poll every 3s until complete/failed. */
export function useEarningsScan() {
  const [scanId, setScanId] = useState<string | null>(null);

  const start = useMutation({
    mutationFn: async (daysAhead: number) => {
      const { data } = await api.post<{ scan_id: string; status: string }>(
        "/earnings/scan",
        { days_ahead: daysAhead },
      );
      return data;
    },
    onSuccess: (data) => setScanId(data.scan_id),
  });

  const scan = useQuery({
    queryKey: ["earnings-scan", scanId],
    queryFn: async () => {
      const { data } = await api.get<EarningsScanDoc>(`/earnings/scan/${scanId}`);
      return data;
    },
    enabled: scanId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "complete" || status === "failed" ? false : 3000;
    },
  });

  const status = start.isPending
    ? "running"
    : (scanId ? (scan.data?.status ?? "running") : "idle");

  return {
    startScan: (daysAhead: number) => start.mutate(daysAhead),
    scan: scan.data,
    // pending (not yet claimed) and running both read as "scanning" for the UI
    isScanning: status === "pending" || status === "running",
    status,
    startError: start.isError,
  };
}

/** Direct enqueue — no chat step. The crew picks the job up on its next poll. */
export function useAnalyzeTickers() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (tickers: string[]) => {
      const { data } = await api.post<{ enqueued: string[] }>("/earnings/analyze", {
        tickers,
      });
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["queue"] }),
  });
}

/** Post-earnings move log for the candidate detail card (fetched on open). */
export function useEarningsHistory(ticker: string | null) {
  return useQuery({
    queryKey: ["earnings-history", ticker],
    queryFn: async () => {
      const { data } = await api.get<EarningsHistory>(`/earnings/history/${ticker}`);
      return data;
    },
    enabled: ticker !== null,
    staleTime: 24 * 60 * 60 * 1000, // backend caches 24h anyway
  });
}

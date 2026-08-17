// Pull-cost breakdown for a ticker (specs/024-delta-data-pulls, US1).
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { PullMetrics } from "../api/types";

export function usePullMetrics(ticker: string, limit = 1) {
  return useQuery({
    queryKey: ["pull-metrics", ticker.toUpperCase(), limit],
    queryFn: async () => {
      const { data } = await api.get<PullMetrics>(`/stocks/${ticker}/pull-metrics`, {
        params: { limit },
      });
      return data;
    },
    enabled: !!ticker,
    // 404 = never pulled, which is an empty state rather than an error.
    retry: false,
    // No polling anywhere in this app; the queue-drain handler invalidates us.
    refetchInterval: false,
  });
}

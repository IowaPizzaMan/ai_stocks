// React Query hooks for the /market endpoints (NYMO/NAMO breadth + SPY,
// divergence state, and the market-wide feed events derived from it).
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { MarketBreadth, MarketFlowEvent } from "../api/types";

// Breadth is recomputed once a day by the agent-runner — no point refetching
// on every window focus.
const DAY_MS = 24 * 60 * 60 * 1000;

export function useMarketBreadth(lookbackDays = 60) {
  return useQuery({
    queryKey: ["market-breadth", lookbackDays],
    queryFn: async () => {
      const { data } = await api.get<MarketBreadth>("/market/breadth", {
        params: { lookback_days: lookbackDays },
      });
      return data;
    },
    staleTime: DAY_MS,
  });
}

export function useMarketFlowEvents(limit = 3) {
  return useQuery({
    queryKey: ["market-flow-events", limit],
    queryFn: async () => {
      const { data } = await api.get<MarketFlowEvent[]>("/market/flow-events", {
        params: { limit },
      });
      return data;
    },
    staleTime: DAY_MS,
  });
}

// React Query hooks for the market-wide /institutional flow feed
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { InstitutionalFlowEvent, InstitutionalFlowResponse } from "../api/types";

export interface InstitutionalFlowFilters {
  action?: string;
  fund?: string;
  ticker?: string;
  min_notability?: string;
}

export function useInstitutionalFlow(filters: InstitutionalFlowFilters = {}) {
  return useInfiniteQuery({
    queryKey: ["institutional-flow", filters],
    queryFn: async ({ pageParam }) => {
      const { data } = await api.get<InstitutionalFlowResponse>("/institutional/flow", {
        params: { page: pageParam, page_size: 20, ...filters },
      });
      return data;
    },
    initialPageParam: 1,
    getNextPageParam: (last) =>
      last.page * last.page_size < last.total ? last.page + 1 : undefined,
  });
}

/** Flow history for one ticker — "view full history" from Stock Detail. */
export function useTickerFlow(ticker: string) {
  return useQuery({
    queryKey: ["institutional-flow", "ticker", ticker.toUpperCase()],
    queryFn: async () => {
      const { data } = await api.get<InstitutionalFlowEvent[]>(
        `/institutional/flow/${ticker.toUpperCase()}`,
      );
      return data;
    },
    enabled: !!ticker,
  });
}

/** Backs the "Scan Now" button — the agent-runner picks the request up
 * out-of-band, so results only appear on a later refresh. */
export function useTriggerInstitutionalScan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<{ status: string; message: string }>(
        "/institutional/scan",
      );
      return data;
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["institutional-flow"] }),
  });
}

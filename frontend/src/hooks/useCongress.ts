// Congress trading disclosures — specs/028-dashboard-tweaks-batch US4.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type {
  CongressSummaryResponse,
  CongressTradesResponse,
} from "../api/types";

export interface CongressFilters {
  ticker?: string;
  politician?: string;
  chamber?: string;
}

export function useCongressTrades(filters: CongressFilters = {}) {
  return useQuery({
    queryKey: ["congress", "trades", filters],
    queryFn: async () => {
      const { data } = await api.get<CongressTradesResponse>("/congress/trades", {
        params: filters,
      });
      return data;
    },
  });
}

export function useCongressSummary() {
  return useQuery({
    queryKey: ["congress", "summary"],
    queryFn: async () => {
      const { data } = await api.get<CongressSummaryResponse>("/congress/summary");
      return data;
    },
  });
}

export function useCongressRefresh() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<{ status: string; job_id: string }>("/congress/refresh");
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["queue"] }),
  });
}

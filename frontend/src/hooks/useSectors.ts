// React Query hooks for the /sectors endpoints
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { AnalysisFeedItem, SectorSummary } from "../api/types";

export function useSectors() {
  return useQuery({
    queryKey: ["sectors"],
    queryFn: async () => {
      const { data } = await api.get<SectorSummary[]>("/sectors");
      return data;
    },
  });
}

export function useSectorAnalysis(sector: string) {
  return useQuery({
    queryKey: ["sector", sector],
    queryFn: async () => {
      const { data } = await api.get<AnalysisFeedItem[]>(`/sectors/${encodeURIComponent(sector)}`);
      return data;
    },
    enabled: !!sector,
  });
}

// Sector ETF comparison chart — specs/028-dashboard-tweaks-batch US5.
// Query keyed on the window so switching it fetches (and caches) separately.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { SectorEtfSeriesResponse, SectorEtfWindow } from "../api/types";

export function useSectorEtfSeries(window: SectorEtfWindow) {
  return useQuery({
    queryKey: ["sector-etf-series", window],
    queryFn: async () => {
      const { data } = await api.get<SectorEtfSeriesResponse>("/sectors/etf-series", {
        params: { window },
      });
      return data;
    },
  });
}

export function useSectorEtfSeriesRefresh() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<{ status: string; job_id: string }>(
        "/sectors/etf-series/refresh",
      );
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["queue"] }),
  });
}

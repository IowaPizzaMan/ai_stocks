// Top Traded Stocks panel — specs/028-dashboard-tweaks-batch US6.
// No refetchInterval anywhere in this app; the queue-drain handler in
// useQueue.ts invalidates ["most-actives"] once the refresh job completes.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { MostActivesResponse } from "../api/types";

export function useMostActives() {
  return useQuery({
    queryKey: ["most-actives"],
    queryFn: async () => {
      const { data } = await api.get<MostActivesResponse>("/market/most-actives");
      return data;
    },
  });
}

export function useMostActivesRefresh() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<{ status: string; job_id: string }>(
        "/market/most-actives/refresh",
      );
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["queue"] }),
  });
}

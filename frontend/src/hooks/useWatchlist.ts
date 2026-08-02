// React Query hooks for /watchlist endpoints
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { WatchlistItem } from "../api/types";

export function useWatchlist() {
  return useQuery({
    queryKey: ["watchlist"],
    queryFn: async () => {
      const { data } = await api.get<{ items: WatchlistItem[]; count: number }>("/watchlist");
      return data;
    },
  });
}

export function useAddToWatchlist() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (ticker: string) => {
      const { data } = await api.post(`/watchlist/${ticker.toUpperCase()}`);
      return data as WatchlistItem;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["watchlist"] }),
  });
}

export function useRemoveFromWatchlist() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (ticker: string) => {
      const { data } = await api.delete(`/watchlist/${ticker.toUpperCase()}`);
      return data as { removed: string };
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["watchlist"] }),
  });
}

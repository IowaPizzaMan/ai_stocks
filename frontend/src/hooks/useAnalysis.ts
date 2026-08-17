// React Query hooks for /analysis + /stocks endpoints
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { api } from "../api/client";
import type { Analysis, FeedResponse } from "../api/types";

export interface FeedFilters {
  ticker?: string; // substring match, server-side (FilterBar search input)
  signal?: string;
  sector?: string;
  conviction?: string;
}

export function useFeed(filters: FeedFilters = {}) {
  return useInfiniteQuery({
    queryKey: ["feed", filters],
    queryFn: async ({ pageParam }) => {
      const { data } = await api.get<FeedResponse>("/analysis/feed", {
        params: { page: pageParam, page_size: 60, ...filters },
      });
      return data;
    },
    initialPageParam: 1,
    getNextPageParam: (last) =>
      last.page * last.page_size < last.total ? last.page + 1 : undefined,
  });
}

export function useTickerAnalysis(ticker: string) {
  return useQuery({
    queryKey: ["analysis", ticker.toUpperCase()],
    queryFn: async () => {
      const { data } = await api.get<Analysis | null>(`/analysis/${ticker}`);
      return data;
    },
    enabled: !!ticker,
  });
}

export function useTickerRecord(ticker: string) {
  return useQuery({
    queryKey: ["ticker", ticker.toUpperCase()],
    queryFn: async () => {
      const { data } = await api.get(`/stocks/${ticker}`);
      return data as { ticker: string; status: string; name?: string; sector?: string };
    },
    enabled: !!ticker,
    retry: false, // 404 = unknown ticker, don't hammer
  });
}

// Destructive: purges the ticker and all its stored data (specs/023-remove-stocks).
export function useDeleteTicker() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (ticker: string) => {
      try {
        const { data } = await api.delete(`/tickers/${ticker.toUpperCase()}`);
        return data as { deleted: string };
      } catch (err) {
        // Already gone is not a failure — see useRemoveFromWatchlist (FR-019).
        if (axios.isAxiosError(err) && err.response?.status === 404) {
          return { deleted: ticker.toUpperCase() };
        }
        throw err;
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["feed"] });
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    },
  });
}

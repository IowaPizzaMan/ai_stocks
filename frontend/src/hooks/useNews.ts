// The mixed general/stock/FMP-article news stream — specs/035-chat-and-news-upgrade.
// Supersedes useMarketNews.ts on the News tab (contracts/news-api.md); that
// hook and /market/news are left in place unchanged for now (research.md R1).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { NewsFeedFilters, NewsFeedResponse } from "../api/types";

export function useNews(filters: NewsFeedFilters = {}) {
  return useQuery({
    queryKey: ["news", filters],
    queryFn: async () => {
      const { data } = await api.get<NewsFeedResponse>("/news", {
        params: {
          source_type: filters.sourceType,
          ticker: filters.ticker,
          limit: filters.limit,
        },
      });
      return data;
    },
  });
}

export function useNewsRefresh() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<{ status: string; job_id: string }>("/news/refresh");
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["queue"] }),
  });
}

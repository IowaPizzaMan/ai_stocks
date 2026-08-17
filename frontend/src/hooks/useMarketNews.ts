// Market-wide headlines for the Stocks page — specs/022-market-news-feed.
//
// Takes no arguments and puts no filter state in the query key, so the page's
// filter bar structurally cannot affect it (FR-001b). staleTime matches the
// backend's 60-minute window so in-session navigation doesn't even reach the
// API, and refetchInterval stays unset — this app never polls (FR-010).
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { MarketNewsResponse } from "../api/types";

const HOUR_MS = 60 * 60 * 1000;

export function useMarketNews() {
  return useQuery({
    queryKey: ["market-news"],
    queryFn: async () => {
      const { data } = await api.get<MarketNewsResponse>("/market/news");
      return data;
    },
    staleTime: HOUR_MS,
  });
}

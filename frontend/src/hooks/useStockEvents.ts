// specs/037-stocks-conviction-and-activity — GET /events (US3 activity feed)
// and GET /events/{ticker} (US5 per-stock change history). Plain paged
// useQuery, not infinite-scroll — the activity feed has discrete forward/back
// paging controls (FR-020), unlike the main board's "Load more".
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { StockEventsResponse, TickerChangeHistoryResponse } from "../api/types";

export function useActivityFeed(page: number, pageSize = 20) {
  return useQuery({
    queryKey: ["stock-events", page, pageSize],
    queryFn: async () => {
      const { data } = await api.get<StockEventsResponse>("/events", {
        params: { page, page_size: pageSize },
      });
      return data;
    },
  });
}

export function useChangeHistory(ticker: string, limit = 20) {
  return useQuery({
    queryKey: ["change-history", ticker.toUpperCase(), limit],
    queryFn: async () => {
      const { data } = await api.get<TickerChangeHistoryResponse>(
        `/events/${ticker.toUpperCase()}`,
        { params: { limit } },
      );
      return data;
    },
    enabled: !!ticker,
  });
}

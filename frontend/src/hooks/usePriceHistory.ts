// Price bars for charts, at the bar resolution matching each timeframe.
import { useQueries, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { OHLCVBar, PriceResponse, StockFinancials } from "../api/types";
import { TIMEFRAME_RESOLUTION, type Timeframe } from "../lib/strat/displayWindow";

async function fetchBars(ticker: string, resolution: string): Promise<OHLCVBar[]> {
  const { data } = await api.get<PriceResponse>(`/stocks/${ticker}/price`, {
    params: { resolution },
  });
  return data.bars;
}

export function useStockPriceHistory(ticker: string, timeframes: Timeframe[]) {
  const resolutions = [...new Set(timeframes.map((tf) => TIMEFRAME_RESOLUTION[tf]))];

  const results = useQueries({
    queries: resolutions.map((resolution) => ({
      queryKey: ["price", ticker.toUpperCase(), resolution],
      queryFn: () => fetchBars(ticker, resolution),
      enabled: !!ticker,
      staleTime: 60 * 60 * 1000,
    })),
  });

  const byResolution: Partial<Record<string, OHLCVBar[]>> = {};
  resolutions.forEach((resolution, i) => {
    byResolution[resolution] = results[i].data;
  });

  const byTimeframe: Partial<Record<Timeframe, OHLCVBar[]>> = {};
  for (const tf of timeframes) {
    byTimeframe[tf] = byResolution[TIMEFRAME_RESOLUTION[tf]];
  }

  return {
    data: byTimeframe,
    isLoading: results.some((r) => r.isLoading),
  };
}

export function useStockSignals(ticker: string) {
  return useQuery({
    queryKey: ["signals", ticker.toUpperCase()],
    queryFn: async () => {
      const { data } = await api.get(`/stocks/${ticker}/signals`);
      return data as { ticker: string; timestamp: string } & import("../api/types").SubReports;
    },
    enabled: !!ticker,
    retry: false,
  });
}

export function useStockFinancials(ticker: string) {
  return useQuery({
    queryKey: ["financials", ticker.toUpperCase()],
    queryFn: async () => {
      const { data } = await api.get<StockFinancials>(`/stocks/${ticker}/financials`);
      return data;
    },
    enabled: !!ticker,
    retry: false,
  });
}

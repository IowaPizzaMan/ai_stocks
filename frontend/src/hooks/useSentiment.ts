// specs/028-dashboard-tweaks-batch US3 — set/clear the like/dislike tag.
// No optimistic update: PUT's toggle-off semantics mean the server decides
// the resulting state (contracts/stock-sentiment-api.md), so guessing it
// client-side would flicker on the toggle-off case.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Sentiment } from "../api/types";

interface SentimentResponse {
  ticker: string;
  sentiment: Sentiment | null;
}

export function useSetSentiment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ ticker, sentiment }: { ticker: string; sentiment: Sentiment }) => {
      const { data } = await api.put(`/stocks/${ticker.toUpperCase()}/sentiment`, { sentiment });
      return data as SentimentResponse;
    },
    onSuccess: (_data, { ticker }) => {
      queryClient.invalidateQueries({ queryKey: ["ticker", ticker.toUpperCase()] });
      queryClient.invalidateQueries({ queryKey: ["feed"] });
    },
  });
}

export function useClearSentiment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (ticker: string) => {
      const { data } = await api.delete(`/stocks/${ticker.toUpperCase()}/sentiment`);
      return data as SentimentResponse;
    },
    onSuccess: (_data, ticker) => {
      queryClient.invalidateQueries({ queryKey: ["ticker", ticker.toUpperCase()] });
      queryClient.invalidateQueries({ queryKey: ["feed"] });
    },
  });
}

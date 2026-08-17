// React Query hooks for /queue endpoints (Pull ticker / Run All / status)
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { EnqueueResponse, PullMode, QueueStatus } from "../api/types";

/** Queue state. Polls while anything is pending/running so the UI notices
 * completions, then goes quiet (the app is otherwise manual-refresh). */
export function useQueueStatus() {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: ["queue"],
    queryFn: async () => {
      const { data } = await api.get<QueueStatus>("/queue");
      return data;
    },
    refetchInterval: (query) => {
      const s = query.state.data;
      const busy = (s?.pending_count ?? 0) + (s?.running_count ?? 0) > 0;
      if (!busy && query.state.dataUpdateCount > 1) {
        // a batch just drained — pull in whatever analyses it produced
        queryClient.invalidateQueries({ queryKey: ["feed"] });
        queryClient.invalidateQueries({ queryKey: ["analysis"] });
        // 024: the pull-cost breakdown lands with the analysis, and this is the
        // only refresh signal it gets (the panel itself never polls).
        queryClient.invalidateQueries({ queryKey: ["pull-metrics"] });
        queryClient.invalidateQueries({ queryKey: ["price"] });
      }
      return busy ? 5000 : false;
    },
  });
}

/** Enqueue a pull. Accepts a bare ticker (delta, the default) or
 * `{ ticker, mode }` for an operator-initiated full refresh (024 US5). */
export function useEnqueueTicker() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: string | { ticker: string; mode?: PullMode }) => {
      const { ticker, mode } = typeof input === "string" ? { ticker: input, mode: undefined } : input;
      const { data } = await api.post<EnqueueResponse>(`/queue/${ticker.toUpperCase()}`, null, {
        params: mode ? { mode } : undefined,
      });
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["queue"] }),
  });
}

export function useEnqueueAll() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post("/queue/all");
      return data as { enqueued: string[]; already_queued: string[]; universe_size: number };
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["queue"] }),
  });
}

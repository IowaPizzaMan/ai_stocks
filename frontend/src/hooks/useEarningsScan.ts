// React Query hooks for /earnings endpoints: the filtered calendar and
// enqueuing selected tickers. spec: specs/025-earnings-page-filters
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { EarningsCalendarResponse } from "../api/types";

/** Date-windowed earnings calendar with actuals/surprise for anything already
 * reported (read-only on the backend — queuing a ticker is an explicit
 * per-row action via useAnalyzeTickers). Query-keyed by the exact window so
 * TanStack Query's per-key caching gives cache reuse across repeated preset
 * clicks and discards stale out-of-order responses for free (FR-027d/e,
 * research.md D8) — no polling (refetchInterval stays off, Constitution
 * Principle V). */
export function useEarningsCalendar(from: string, to: string) {
  return useQuery({
    queryKey: ["earnings-calendar", from, to],
    queryFn: async () => {
      const { data } = await api.get<EarningsCalendarResponse>(
        `/earnings/calendar?from=${from}&to=${to}`,
      );
      return data;
    },
    staleTime: 4 * 60 * 60 * 1000, // backend caches 4h per window; don't hammer on tab focus
    placeholderData: (previous) => previous, // keep prior rows visible while a new window loads (FR-027c)
  });
}

/** Direct enqueue — no chat step. The crew picks the job up on its next poll. */
export function useAnalyzeTickers() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (tickers: string[]) => {
      const { data } = await api.post<{ enqueued: string[] }>("/earnings/analyze", {
        tickers,
      });
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["queue"] }),
  });
}

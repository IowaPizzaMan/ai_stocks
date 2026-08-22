// Manual regenerate control for the cross-stock AI summary panel — specs/027.
// Enqueues the portfolio_digest admin job; the queue drain (useQueueStatus)
// is what eventually invalidates ["portfolio-digest"] once it completes.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

export function usePortfolioDigestRegenerate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<{ status: string; job_id: string }>(
        "/portfolio/digest/regenerate",
      );
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["queue"] }),
  });
}

// React Query hook for GET /market/macro — per-sector macro reads, produced
// independently of ticker analysis by the agent-runner's macro worker.
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { MacroReads } from "../api/types";

// Sector reads refresh at most weekly on the backend — no point refetching
// on every window focus.
const DAY_MS = 24 * 60 * 60 * 1000;

export function useMacroReads() {
  return useQuery({
    queryKey: ["macro-reads"],
    queryFn: async () => {
      const { data } = await api.get<MacroReads>("/market/macro");
      return data;
    },
    staleTime: DAY_MS,
  });
}

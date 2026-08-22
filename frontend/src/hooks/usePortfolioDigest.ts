// Cross-stock AI summary panel on the Stocks page — specs/027.
//
// Takes no arguments and puts no filter state in the query key, mirroring
// useMarketNews's filter-independence (FR-007a): the grid's filter bar can
// never affect what this reads or when it refetches. No refetchInterval —
// this app never polls; busy/in-progress state comes from useQueueStatus.
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { PortfolioDigestResponse } from "../api/types";

export function usePortfolioDigest() {
  return useQuery({
    queryKey: ["portfolio-digest"],
    queryFn: async () => {
      const { data } = await api.get<PortfolioDigestResponse>("/portfolio/digest");
      return data;
    },
  });
}

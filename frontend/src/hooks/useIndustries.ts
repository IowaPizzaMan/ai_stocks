// Spec: specs/029-company-profile-tweaks/contracts/sector-and-industry.md (US5)
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { IndustriesResponse } from "../api/types";

export function useIndustries() {
  return useQuery({
    queryKey: ["industries"],
    queryFn: async () => {
      const { data } = await api.get<IndustriesResponse>("/stocks/industries");
      return data.industries;
    },
    refetchInterval: false,
  });
}

// Spec: specs/029-company-profile-tweaks/contracts/company-profile-api.md
//
// All three reads are cache-only on the backend (never issue a provider
// call — Principle IV), so refetchInterval stays false everywhere in this
// app (constitution) and a 1h staleTime matches usePriceHistory.
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type {
  CompanyProfile,
  EmployeeCountResponse,
  PeersResponse,
} from "../api/types";

const STALE_TIME = 60 * 60 * 1000;

export function useCompanyProfile(ticker: string) {
  return useQuery({
    queryKey: ["company-profile", ticker.toUpperCase()],
    queryFn: async () => {
      const { data } = await api.get<CompanyProfile>(`/stocks/${ticker}/profile`);
      return data;
    },
    enabled: !!ticker,
    staleTime: STALE_TIME,
    refetchInterval: false,
    // A 404 means "no profile fetched yet" — a valid, expected answer, not
    // a transient failure worth retrying (FR-009).
    retry: (failureCount, error: unknown) => {
      const status = (error as { response?: { status?: number } })?.response?.status;
      if (status === 404) return false;
      return failureCount < 2;
    },
  });
}

export function usePeers(ticker: string) {
  return useQuery({
    queryKey: ["company-peers", ticker.toUpperCase()],
    queryFn: async () => {
      const { data } = await api.get<PeersResponse>(`/stocks/${ticker}/peers`);
      return data;
    },
    enabled: !!ticker,
    staleTime: STALE_TIME,
    refetchInterval: false,
  });
}

export function useEmployeeCounts(ticker: string) {
  return useQuery({
    queryKey: ["employee-counts", ticker.toUpperCase()],
    queryFn: async () => {
      const { data } = await api.get<EmployeeCountResponse>(`/stocks/${ticker}/employee-count`);
      return data;
    },
    enabled: !!ticker,
    staleTime: STALE_TIME,
    refetchInterval: false,
  });
}

// React Query hooks for the economics dashboard endpoints
// (specs/026-macro-market-dashboard/contracts/macro-api.md).
//
// Four independent queries, not one composite — FR-027 requires each Macro
// page section to render and fail on its own, and a single combined query
// would couple their loading/error states together.
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { EconomicCalendar, EconomicIndicators, RiskPremium, TreasuryCurve } from "../api/types";

// All four datasets refresh at most once a day (agent-runner's economics
// worker) — no point refetching on every window focus.
const DAY_MS = 24 * 60 * 60 * 1000;

export function useTreasuryCurve(lookbackDays = 180) {
  return useQuery({
    queryKey: ["treasury-curve", lookbackDays],
    queryFn: async () => {
      const { data } = await api.get<TreasuryCurve>("/market/treasury-curve", {
        params: { lookback_days: lookbackDays },
      });
      return data;
    },
    staleTime: DAY_MS,
  });
}

export function useEconomicCalendar(forwardDays = 14, backDays = 7) {
  return useQuery({
    queryKey: ["economic-calendar", forwardDays, backDays],
    queryFn: async () => {
      const { data } = await api.get<EconomicCalendar>("/market/economic-calendar", {
        params: { forward_days: forwardDays, back_days: backDays },
      });
      return data;
    },
    staleTime: DAY_MS,
  });
}

export function useEconomicIndicators() {
  return useQuery({
    queryKey: ["economic-indicators"],
    queryFn: async () => {
      const { data } = await api.get<EconomicIndicators>("/market/economic-indicators");
      return data;
    },
    staleTime: DAY_MS,
  });
}

export function useRiskPremium() {
  return useQuery({
    queryKey: ["risk-premium"],
    queryFn: async () => {
      const { data } = await api.get<RiskPremium>("/market/risk-premium");
      return data;
    },
    staleTime: DAY_MS,
  });
}

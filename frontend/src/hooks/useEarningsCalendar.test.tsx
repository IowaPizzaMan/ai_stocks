import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../api/client";
import type { EarningsCalendarResponse } from "../api/types";
import { useEarningsCalendar } from "./useEarningsScan";

vi.mock("../api/client", () => ({ api: { get: vi.fn() } }));

afterEach(() => vi.clearAllMocks());

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
);

const RESPONSE: EarningsCalendarResponse = {
  entries: [],
  total_before_screen: 0,
  stale: false,
  fetched_at: "2026-08-17T12:00:00Z",
};

test("requests /earnings/calendar with the given from/to window", async () => {
  vi.mocked(api.get).mockResolvedValue({ data: RESPONSE });

  const { result } = renderHook(() => useEarningsCalendar("2026-08-15", "2026-08-19"), { wrapper });

  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(api.get).toHaveBeenCalledWith("/earnings/calendar?from=2026-08-15&to=2026-08-19");
  expect(result.current.data).toEqual(RESPONSE);
});

test("uses a query key scoped to the exact window", async () => {
  vi.mocked(api.get).mockResolvedValue({ data: RESPONSE });
  const client = new QueryClient();
  const localWrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );

  const { result } = renderHook(() => useEarningsCalendar("2026-08-15", "2026-08-19"), {
    wrapper: localWrapper,
  });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));

  expect(client.getQueryData(["earnings-calendar", "2026-08-15", "2026-08-19"])).toEqual(RESPONSE);
});

test("does not refetch within the cache staleTime for the same window", async () => {
  vi.mocked(api.get).mockResolvedValue({ data: RESPONSE });
  const client = new QueryClient();
  const localWrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );

  const first = renderHook(() => useEarningsCalendar("2026-08-15", "2026-08-19"), {
    wrapper: localWrapper,
  });
  await waitFor(() => expect(first.result.current.isSuccess).toBe(true));
  expect(api.get).toHaveBeenCalledTimes(1);

  // A second mount for the same window must serve from the cache, not refetch.
  const second = renderHook(() => useEarningsCalendar("2026-08-15", "2026-08-19"), {
    wrapper: localWrapper,
  });
  await waitFor(() => expect(second.result.current.isSuccess).toBe(true));
  expect(api.get).toHaveBeenCalledTimes(1);
});

test("a slow response for an abandoned window never overwrites the current window's data", async () => {
  // Regression for FR-027e / research.md D8: TanStack Query keys by [from, to],
  // so a response for a previous key can never land on the current one.
  const OLD: EarningsCalendarResponse = { ...RESPONSE, total_before_screen: 1 };
  const NEW: EarningsCalendarResponse = { ...RESPONSE, total_before_screen: 2 };

  let resolveOld: (v: { data: EarningsCalendarResponse }) => void = () => {};
  const oldPromise = new Promise<{ data: EarningsCalendarResponse }>((resolve) => {
    resolveOld = resolve;
  });

  vi.mocked(api.get).mockImplementationOnce(() => oldPromise as never);
  vi.mocked(api.get).mockResolvedValueOnce({ data: NEW });

  const client = new QueryClient();
  const localWrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );

  const { result, rerender } = renderHook(
    ({ from, to }: { from: string; to: string }) => useEarningsCalendar(from, to),
    { wrapper: localWrapper, initialProps: { from: "2026-08-01", to: "2026-08-05" } },
  );

  // Move to the new window before the old request resolves.
  rerender({ from: "2026-08-15", to: "2026-08-19" });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.data).toEqual(NEW);

  // The abandoned request finally resolves — it must not clobber the new window's cache entry.
  resolveOld({ data: OLD });
  await new Promise((r) => setTimeout(r, 0));
  expect(client.getQueryData(["earnings-calendar", "2026-08-15", "2026-08-19"])).toEqual(NEW);
});

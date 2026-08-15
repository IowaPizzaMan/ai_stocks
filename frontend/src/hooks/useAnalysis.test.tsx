import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../api/client";
import type { Analysis } from "../api/types";
import { useTickerAnalysis } from "./useAnalysis";

vi.mock("../api/client", () => ({ api: { get: vi.fn() } }));

afterEach(() => vi.clearAllMocks());

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
);

test("useTickerAnalysis resolves to null when the API returns no analysis", async () => {
  vi.mocked(api.get).mockResolvedValue({ data: null });

  const { result } = renderHook(() => useTickerAnalysis("ZZZZ"), { wrapper });

  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.data).toBeNull();
});

test("useTickerAnalysis resolves to the fetched analysis object directly", async () => {
  const analysis = { ticker: "AAPL", signal: "bullish", conviction: "high" } as Analysis;
  vi.mocked(api.get).mockResolvedValue({ data: analysis });

  const { result } = renderHook(() => useTickerAnalysis("AAPL"), { wrapper });

  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.data).toEqual(analysis);
});

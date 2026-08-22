// specs/028-dashboard-tweaks-batch US3 — set/clear mutations for like/dislike.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { api } from "../api/client";
import { useClearSentiment, useSetSentiment } from "./useSentiment";

vi.mock("../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

afterEach(() => vi.clearAllMocks());

function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidated: unknown[][] = [];
  const originalInvalidate = client.invalidateQueries.bind(client);
  client.invalidateQueries = (opts) => {
    invalidated.push((opts as { queryKey?: unknown[] })?.queryKey ?? []);
    return originalInvalidate(opts);
  };
  return {
    client,
    invalidated,
    Wrapper: ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  };
}

describe("useSetSentiment", () => {
  test("PUTs the sentiment and invalidates the ticker record and feed", async () => {
    vi.mocked(api.put).mockResolvedValue({ data: { ticker: "AAPL", sentiment: "liked" } });
    const { Wrapper, invalidated } = wrapper();
    const { result } = renderHook(() => useSetSentiment(), { wrapper: Wrapper });

    result.current.mutate({ ticker: "AAPL", sentiment: "liked" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.put).toHaveBeenCalledWith("/stocks/AAPL/sentiment", { sentiment: "liked" });
    expect(invalidated).toContainEqual(["ticker", "AAPL"]);
    expect(invalidated).toContainEqual(["feed"]);
  });
});

describe("useClearSentiment", () => {
  test("DELETEs the sentiment and invalidates the ticker record and feed", async () => {
    vi.mocked(api.delete).mockResolvedValue({ data: { ticker: "AAPL", sentiment: null } });
    const { Wrapper, invalidated } = wrapper();
    const { result } = renderHook(() => useClearSentiment(), { wrapper: Wrapper });

    result.current.mutate("AAPL");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.delete).toHaveBeenCalledWith("/stocks/AAPL/sentiment");
    expect(invalidated).toContainEqual(["ticker", "AAPL"]);
    expect(invalidated).toContainEqual(["feed"]);
  });
});

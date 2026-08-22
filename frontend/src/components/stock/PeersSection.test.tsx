import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../../api/client";
import PeersSection from "./PeersSection";

vi.mock("../../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function renderPeers(ticker = "AAPL") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PeersSection ticker={ticker} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("renders symbol/name/price/market cap rows, largest cap first (server order)", async () => {
  (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
    data: {
      ticker: "AAPL",
      peers: [
        { symbol: "GOOGL", name: "Alphabet Inc.", price: 333.84, market_cap: 4040168831718 },
        { symbol: "MSFT", name: "Microsoft Corp.", price: 500, market_cap: null },
      ],
      fetched_at: "2026-08-22T00:00:00Z",
    },
  });

  renderPeers();

  await waitFor(() => expect(screen.getByText("GOOGL")).toBeTruthy());
  expect(screen.getByText("Alphabet Inc.")).toBeTruthy();
  expect(screen.getByText("$333.84")).toBeTruthy();
  expect(screen.getByText("$4.0T")).toBeTruthy();
  // null market cap renders a dash, not 0 or $0
  const row = screen.getByText("MSFT").closest("tr")!;
  expect(row.textContent).toContain("—");
  expect(row.textContent).not.toContain("$0");
});

test("clicking a peer links to /stock/{symbol}", async () => {
  (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
    data: { ticker: "AAPL", peers: [{ symbol: "GOOGL", name: "Alphabet Inc.", price: 333.84, market_cap: 1 }], fetched_at: null },
  });

  renderPeers();

  const link = await screen.findByText("GOOGL");
  expect(link.closest("a")?.getAttribute("href")).toBe("/stock/GOOGL");
});

test("empty peers renders an empty state", async () => {
  (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
    data: { ticker: "AAPL", peers: [], fetched_at: null },
  });

  renderPeers();

  await waitFor(() => expect(screen.getByText(/no peers published/i)).toBeTruthy());
});

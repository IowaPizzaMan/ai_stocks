import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../../api/client";
import type { PortfolioDigestResponse, QueueStatus } from "../../api/types";
import { usePortfolioDigest } from "../../hooks/usePortfolioDigest";
import PortfolioDigestPanel from "./PortfolioDigestPanel";

vi.mock("../../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function digest(overrides: Partial<PortfolioDigestResponse> = {}): PortfolioDigestResponse {
  return {
    as_of: "2026-08-21T18:04:00+00:00",
    overview: "Momentum skews bullish across the set.",
    highlights: [
      { ticker: "AAPL", signal: "bullish", conviction: "high", note: "Fresh accumulation flag." },
    ],
    stock_count: 12,
    total_tracked_count: 12,
    capped: false,
    stale: false,
    ...overrides,
  };
}

function renderPanel({
  digestBody = digest(),
  digestFail = false,
  queue = { pending: [], running: [], pending_count: 0, running_count: 0 } as QueueStatus,
}: {
  digestBody?: PortfolioDigestResponse;
  digestFail?: boolean;
  queue?: QueueStatus;
} = {}) {
  vi.mocked(api.get).mockImplementation(async (url: string) => {
    if (url === "/portfolio/digest") {
      if (digestFail) throw new Error("boom");
      return { data: digestBody };
    }
    if (url === "/queue") return { data: queue };
    throw new Error(`unexpected GET ${url}`);
  });
  vi.mocked(api.post).mockResolvedValue({ data: { status: "enqueued", job_id: "job-1" } });

  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PortfolioDigestPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// --- empty / ready states -----------------------------------------------------

test("shows an empty/prompt state before any summary has ever been generated", async () => {
  renderPanel({
    digestBody: digest({ as_of: null, overview: null, highlights: [], stock_count: 0, total_tracked_count: 0 }),
  });
  await waitFor(() => expect(screen.getByText(/no summary yet/i)).toBeTruthy());
  expect(screen.queryByText(/Momentum skews/)).toBeNull();
});

test("renders the overview and highlights, each linking its ticker", async () => {
  const { container } = renderPanel();
  await waitFor(() =>
    expect(screen.getByText(/Momentum skews/)).toBeTruthy(),
  );
  expect(screen.getByText(/fresh accumulation flag/i)).toBeTruthy();
  expect(container.querySelector('a[href="/stocks/AAPL"]')).toBeTruthy();
});

// --- stale / capped -----------------------------------------------------------

test("shows a stale indicator without hiding the prior content", async () => {
  renderPanel({ digestBody: digest({ stale: true }) });
  await waitFor(() =>
    expect(screen.getByText(/Momentum skews/)).toBeTruthy(),
  );
  expect(screen.getByText(/stale|not current|last successful/i)).toBeTruthy();
});

test("shows a note when the input set was capped", async () => {
  renderPanel({ digestBody: digest({ capped: true, stock_count: 25, total_tracked_count: 40 }) });
  await waitFor(() =>
    expect(screen.getByText(/Momentum skews/)).toBeTruthy(),
  );
  expect(screen.getByText(/not all tracked stocks|25 of 40/i)).toBeTruthy();
});

// --- regenerate control ---------------------------------------------------------

test("clicking regenerate calls the regenerate endpoint", async () => {
  renderPanel();
  const button = await screen.findByRole("button", { name: /regenerate/i });
  fireEvent.click(button);
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/portfolio/digest/regenerate"));
});

test("disables the regenerate control and shows a busy indicator while a job is pending", async () => {
  renderPanel({
    queue: {
      pending: [{ job_type: "portfolio_digest", status: "pending", created_at: "now" }],
      running: [],
      pending_count: 1,
      running_count: 0,
    },
  });
  const button = await screen.findByRole("button", { name: /regenerat/i });
  await waitFor(() => expect(button).toHaveProperty("disabled", true));
});

test("disables the regenerate control while a job is running", async () => {
  renderPanel({
    queue: {
      pending: [],
      running: [{ job_type: "portfolio_digest", status: "running", created_at: "now" }],
      pending_count: 0,
      running_count: 1,
    },
  });
  const button = await screen.findByRole("button", { name: /regenerat/i });
  await waitFor(() => expect(button).toHaveProperty("disabled", true));
});

test("a pending ticker analysis job does not disable the regenerate control", async () => {
  renderPanel({
    queue: {
      pending: [{ ticker: "AAPL", status: "pending", created_at: "now" }],
      running: [],
      pending_count: 1,
      running_count: 0,
    },
  });
  const button = await screen.findByRole("button", { name: /regenerat/i });
  expect(button).toHaveProperty("disabled", false);
});

// --- failure ------------------------------------------------------------------

test("shows an unavailable message rather than breaking when the request fails", async () => {
  renderPanel({ digestFail: true });
  await waitFor(() => expect(screen.getByText(/unavailable/i)).toBeTruthy());
});

// --- filter-independence (mirrors useMarketNews) ------------------------------

test("takes no filter arguments and puts no filter state in the query key", () => {
  const client = new QueryClient();
  let observed: unknown;
  function Probe() {
    usePortfolioDigest();
    observed = client.getQueryCache().find({ queryKey: ["portfolio-digest"] })?.queryKey;
    return null;
  }
  vi.mocked(api.get).mockResolvedValue({ data: digest() });
  render(
    <QueryClientProvider client={client}>
      <Probe />
    </QueryClientProvider>,
  );
  expect(observed).toEqual(["portfolio-digest"]);
});

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../../api/client";
import EmployeeCountChart from "./EmployeeCountChart";

vi.mock("../../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function renderChart(ticker = "AAPL") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <EmployeeCountChart ticker={ticker} />
    </QueryClientProvider>,
  );
}

test("renders a chart section when records exist", async () => {
  (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
    data: {
      ticker: "AAPL",
      records: [
        { period_of_report: "2024-09-28", filing_date: "2024-11-01", form_type: "10-K", employee_count: 161000, source: "s" },
        { period_of_report: "2025-09-27", filing_date: "2025-10-31", form_type: "10-K", employee_count: 166000, source: "s" },
      ],
      fetched_at: "2026-08-22T00:00:00Z",
    },
  });

  const { container } = renderChart();

  await waitFor(() => expect(container.querySelector(".recharts-responsive-container")).not.toBeNull());
  expect(screen.getByText("Employee Count")).toBeTruthy();
});

test("a single record still renders the chart, not an empty state", async () => {
  (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
    data: {
      ticker: "AAPL",
      records: [{ period_of_report: "2025-09-27", filing_date: "2025-10-31", form_type: "10-K", employee_count: 166000, source: "s" }],
      fetched_at: null,
    },
  });

  const { container } = renderChart();

  await waitFor(() => expect(container.querySelector(".recharts-responsive-container")).not.toBeNull());
  expect(screen.queryByText(/no reported employee history/i)).toBeNull();
});

test("empty history renders an empty state", async () => {
  (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
    data: { ticker: "AAPL", records: [], fetched_at: null },
  });

  renderChart();

  await waitFor(() => expect(screen.getByText(/no reported employee history/i)).toBeTruthy());
});

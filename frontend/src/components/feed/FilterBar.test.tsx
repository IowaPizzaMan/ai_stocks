// specs/028-dashboard-tweaks-batch US3 (FR-009) — liked/disliked filter chips.
// specs/029-company-profile-tweaks US5 (FR-024/FR-025) — industry <select>.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useSearchParams } from "react-router-dom";
import { afterEach, describe, expect, test, vi } from "vitest";
import { api } from "../../api/client";
import FilterBar from "./FilterBar";

vi.mock("../../api/client", () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function ParamsProbe() {
  const [params] = useSearchParams();
  return <span data-testid="params">{params.toString()}</span>;
}

function renderBar(initial = "/", { industries = [] as string[] } = {}) {
  (api.get as ReturnType<typeof vi.fn>).mockImplementation((url: string) => {
    if (url === "/stocks/industries") return Promise.resolve({ data: { industries } });
    if (url === "/queue") {
      return Promise.resolve({ data: { pending: [], running: [], pending_count: 0, running_count: 0 } });
    }
    return Promise.resolve({ data: {} });
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initial]}>
        <Routes>
          <Route
            path="/"
            element={
              <>
                <FilterBar />
                <ParamsProbe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("FilterBar sentiment chips", () => {
  test("selecting liked sets ?sentiment=liked", () => {
    renderBar();
    fireEvent.click(screen.getByRole("button", { name: /^liked$/i }));
    expect(screen.getByTestId("params").textContent).toBe("sentiment=liked");
  });

  test("selecting liked again clears it", () => {
    renderBar("/?sentiment=liked");
    fireEvent.click(screen.getByRole("button", { name: /^liked$/i }));
    expect(screen.getByTestId("params").textContent).toBe("");
  });

  test("selecting disliked while liked is active replaces it (shared param)", () => {
    renderBar("/?sentiment=liked");
    fireEvent.click(screen.getByRole("button", { name: /^disliked$/i }));
    expect(screen.getByTestId("params").textContent).toBe("sentiment=disliked");
  });
});

describe("FilterBar industry filter", () => {
  test("the industry select is hidden when no industries are available", async () => {
    renderBar();
    expect(screen.queryByLabelText(/filter feed by industry/i)).toBeNull();
  });

  test("the industry select lists the available industries once loaded", async () => {
    renderBar("/", { industries: ["Consumer Electronics", "Software - Infrastructure"] });
    const select = await screen.findByLabelText(/filter feed by industry/i);
    const options = Array.from(select.querySelectorAll("option")).map((o) => o.textContent);
    expect(options).toEqual(["All industries", "Consumer Electronics", "Software - Infrastructure"]);
  });

  test("selecting an industry sets ?industry=", async () => {
    renderBar("/", { industries: ["Consumer Electronics"] });
    const select = await screen.findByLabelText(/filter feed by industry/i);

    fireEvent.change(select, { target: { value: "Consumer Electronics" } });

    expect(screen.getByTestId("params").textContent).toBe("industry=Consumer+Electronics");
  });

  test("choosing 'All industries' clears the filter", async () => {
    renderBar("/?industry=Consumer+Electronics", { industries: ["Consumer Electronics"] });
    const select = await screen.findByLabelText(/filter feed by industry/i);

    fireEvent.change(select, { target: { value: "" } });

    expect(screen.getByTestId("params").textContent).toBe("");
  });

  test("industry combines with an existing signal filter rather than replacing it", async () => {
    renderBar("/?signal=bullish", { industries: ["Consumer Electronics"] });
    const select = await screen.findByLabelText(/filter feed by industry/i);

    fireEvent.change(select, { target: { value: "Consumer Electronics" } });

    const params = new URLSearchParams(screen.getByTestId("params").textContent ?? "");
    expect(params.get("signal")).toBe("bullish");
    expect(params.get("industry")).toBe("Consumer Electronics");
  });
});

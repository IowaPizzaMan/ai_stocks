import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test } from "vitest";
import App from "./App";

test("renders navbar and feed placeholder", () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(screen.getByText("StockAI")).toBeDefined();
  expect(screen.getByText("Analysis Feed")).toBeDefined();
});

// specs/028-dashboard-tweaks-batch US1 (FR-001) — before this route existed,
// an unmatched path (e.g. the digest panel's old /stocks/<ticker> link) rendered
// a structurally empty <main> with no error, which is what made the blank-page
// bug silent. The catch-all turns that failure class into a visible message.
test("renders a not-found message instead of a blank page for an unmatched route", () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/definitely-not-a-route"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(screen.getByText(/page not found/i)).toBeDefined();
});

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { type ReactNode } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, expect, test } from "vitest";
import EarningsFilterBar from "./EarningsFilterBar";

afterEach(cleanup);

function isoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function addDays(base: Date, days: number): Date {
  const d = new Date(base);
  d.setDate(d.getDate() + days);
  return d;
}

// Small helper component so tests can read the current URL search string
// without reaching into react-router internals.
function CaptureParams({ children, onParams }: { children: ReactNode; onParams: (s: string) => void }) {
  const location = useLocation();
  onParams(location.search);
  return <>{children}</>;
}

function renderBar(initialPath = "/earnings") {
  let capturedParams = "";
  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route
          path="/earnings"
          element={
            <CaptureParams onParams={(p) => (capturedParams = p)}>
              <EarningsFilterBar />
            </CaptureParams>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
  return {
    getParams: () => new URLSearchParams(capturedParams),
  };
}

// --- date presets (US1) --------------------------------------------------------------

test("renders all six date presets", () => {
  renderBar();
  for (const label of ["Today", "±2 days", "Last 7 days", "Next 7 days", "±2 weeks", "±1 month"]) {
    expect(screen.getByRole("button", { name: label })).toBeTruthy();
  }
});

test("±2 days preset is active by default with no URL params", () => {
  renderBar();
  expect(screen.getByRole("button", { name: "±2 days" }).getAttribute("aria-pressed")).toBe("true");
});

test("clicking a preset writes from/to URL params matching the resolved window", () => {
  const { getParams } = renderBar();
  fireEvent.click(screen.getByRole("button", { name: "Last 7 days" }));

  const today = new Date();
  const params = getParams();
  expect(params.get("from")).toBe(isoDate(addDays(today, -7)));
  expect(params.get("to")).toBe(isoDate(today));
});

test("clicking a preset marks it active and populates the custom date inputs", () => {
  renderBar();
  fireEvent.click(screen.getByRole("button", { name: "Next 7 days" }));

  expect(screen.getByRole("button", { name: "Next 7 days" }).getAttribute("aria-pressed")).toBe("true");
  expect(screen.getByRole("button", { name: "±2 days" }).getAttribute("aria-pressed")).toBe("false");

  const today = new Date();
  const startInput = screen.getByLabelText("Custom start date") as HTMLInputElement;
  const endInput = screen.getByLabelText("Custom end date") as HTMLInputElement;
  expect(startInput.value).toBe(isoDate(today));
  expect(endInput.value).toBe(isoDate(addDays(today, 7)));
});

test("typing a custom date that matches no preset clears the active-preset highlight", async () => {
  const { getParams } = renderBar();
  const startInput = screen.getByLabelText("Custom start date");
  fireEvent.change(startInput, { target: { value: "2020-01-01" } });

  await waitFor(() => expect(getParams().get("from")).toBe("2020-01-01"), { timeout: 1000 });

  for (const label of ["Today", "±2 days", "Last 7 days", "Next 7 days", "±2 weeks", "±1 month"]) {
    expect(screen.getByRole("button", { name: label }).getAttribute("aria-pressed")).toBe("false");
  }
});

test("an inverted custom range does not update the URL params", async () => {
  const { getParams } = renderBar();
  const before = getParams().toString();

  const startInput = screen.getByLabelText("Custom start date");
  const endInput = screen.getByLabelText("Custom end date");
  fireEvent.change(startInput, { target: { value: "2026-08-20" } });
  fireEvent.change(endInput, { target: { value: "2026-08-10" } });

  // give the debounce a chance to fire — it must not, since the range is invalid
  await new Promise((r) => setTimeout(r, 500));
  expect(getParams().toString()).toBe(before);
  expect(screen.queryByText(/end date must not be before start date/i)).not.toBeNull();
});

// --- size sliders + big-movers toggle (US3) -------------------------------------------

test("revenue slider defaults to $10M and EPS slider defaults to $0.01", () => {
  renderBar();
  expect((screen.getByLabelText("Minimum revenue") as HTMLInputElement).value).toBe("10000000");
  expect((screen.getByLabelText("Minimum EPS magnitude") as HTMLInputElement).value).toBe("0.01");
});

test("moving the revenue slider writes min_rev without touching from/to", () => {
  const { getParams } = renderBar();
  const before = { from: getParams().get("from"), to: getParams().get("to") };

  fireEvent.change(screen.getByLabelText("Minimum revenue"), { target: { value: "50000000" } });

  const after = getParams();
  expect(after.get("min_rev")).toBe("50000000");
  expect(after.get("from")).toBe(before.from);
  expect(after.get("to")).toBe(before.to);
});

test("moving the EPS slider writes min_eps without touching from/to", () => {
  const { getParams } = renderBar();
  const before = { from: getParams().get("from"), to: getParams().get("to") };

  fireEvent.change(screen.getByLabelText("Minimum EPS magnitude"), { target: { value: "0.5" } });

  const after = getParams();
  expect(after.get("min_eps")).toBe("0.5");
  expect(after.get("from")).toBe(before.from);
  expect(after.get("to")).toBe(before.to);
});

test("big-movers toggle defaults off and writes movers=1 when checked, without touching from/to", () => {
  const { getParams } = renderBar();
  expect((screen.getByLabelText("Big movers only") as HTMLInputElement).checked).toBe(false);
  const before = { from: getParams().get("from"), to: getParams().get("to") };

  fireEvent.click(screen.getByLabelText("Big movers only"));

  const after = getParams();
  expect(after.get("movers")).toBe("1");
  expect(after.get("from")).toBe(before.from);
  expect(after.get("to")).toBe(before.to);
});

test("unchecking big movers removes the movers param", () => {
  const { getParams } = renderBar();
  fireEvent.click(screen.getByLabelText("Big movers only"));
  fireEvent.click(screen.getByLabelText("Big movers only"));
  expect(getParams().get("movers")).toBeNull();
});

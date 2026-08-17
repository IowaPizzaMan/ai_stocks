import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import FullRefreshButton from "./FullRefreshButton";

afterEach(cleanup);

function setup(props: Partial<React.ComponentProps<typeof FullRefreshButton>> = {}) {
  const onRefresh = vi.fn();
  render(<FullRefreshButton ticker="AAPL" onRefresh={onRefresh} {...props} />);
  return { onRefresh };
}

test("reads as distinct from an ordinary pull", () => {
  setup();
  // FR-028 — the operator must not confuse this with Pull ▶
  expect(screen.getByRole("button", { name: /full refresh/i })).toBeTruthy();
});

test("does not fire on a single click", () => {
  // It replaces stored data and spends real API budget, so it confirms first —
  // same pattern as RemoveTickerConfirm.
  const { onRefresh } = setup();
  fireEvent.click(screen.getByRole("button", { name: /full refresh/i }));
  expect(onRefresh).not.toHaveBeenCalled();
});

test("explains what it will do before confirming", () => {
  setup();
  fireEvent.click(screen.getByRole("button", { name: /full refresh/i }));
  // FR-024 — one action covers every delta-maintained dataset
  expect(screen.getByRole("dialog")).toBeTruthy();
  expect(screen.getByText(/re-download/i)).toBeTruthy();
});

test("confirming triggers the refresh", () => {
  const { onRefresh } = setup();
  fireEvent.click(screen.getByRole("button", { name: /full refresh/i }));
  fireEvent.click(screen.getByRole("button", { name: /confirm full refresh/i }));
  expect(onRefresh).toHaveBeenCalledTimes(1);
});

test("cancelling does nothing", () => {
  const { onRefresh } = setup();
  fireEvent.click(screen.getByRole("button", { name: /full refresh/i }));
  fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
  expect(onRefresh).not.toHaveBeenCalled();
  expect(screen.queryByRole("dialog")).toBeNull();
});

test("escape closes the confirm", () => {
  const { onRefresh } = setup();
  fireEvent.click(screen.getByRole("button", { name: /full refresh/i }));
  fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(onRefresh).not.toHaveBeenCalled();
});

test("stays available for a ticker with no stored data", () => {
  // FR-029 — with no baseline it simply behaves as a first-ever pull
  setup({ hasData: false });
  expect(screen.getByRole("button", { name: /full refresh/i })).not.toHaveProperty(
    "disabled",
    true,
  );
});

test("tells the operator when a pull is already running instead of silently dropping the request", () => {
  // research D8 — a running job is too late to upgrade
  setup({ busy: true });
  expect(screen.getByText(/already running/i)).toBeTruthy();
  expect(screen.queryByRole("button", { name: /full refresh/i })).toBeNull();
});

test("shows progress while the refresh is queued", () => {
  setup({ pending: true });
  expect(screen.getByText(/refreshing/i)).toBeTruthy();
});

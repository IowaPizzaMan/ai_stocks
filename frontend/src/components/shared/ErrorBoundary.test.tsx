import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { reportError } from "../../lib/errorLogger";
import ErrorBoundary from "./ErrorBoundary";

vi.mock("../../lib/errorLogger", () => ({
  reportError: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function Bomb(): never {
  throw new Error("kaboom");
}

test("renders children when nothing throws", () => {
  render(
    <ErrorBoundary>
      <p>all good</p>
    </ErrorBoundary>,
  );
  expect(screen.getByText("all good")).toBeDefined();
});

test("catches render errors, shows a fallback, and reports them", () => {
  // React logs the caught error to the console by design; keep test output clean.
  const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

  render(
    <ErrorBoundary>
      <Bomb />
    </ErrorBoundary>,
  );

  expect(screen.getByText("Something went wrong")).toBeDefined();
  expect(reportError).toHaveBeenCalledWith(
    expect.objectContaining({ message: "kaboom" }),
    "ErrorBoundary",
  );

  consoleError.mockRestore();
});

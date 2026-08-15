import { afterEach, expect, test, vi } from "vitest";
import { api } from "../api/client";
import { installGlobalErrorLogging, reportError } from "./errorLogger";

vi.mock("../api/client", () => ({
  api: { post: vi.fn().mockResolvedValue({}) },
}));

afterEach(() => {
  vi.clearAllMocks();
});

function dispatchWindowEvent(type: string, props: Record<string, unknown>) {
  const event = new Event(type);
  Object.assign(event, props);
  window.dispatchEvent(event);
}

test("reportError posts message, stack, component, url and timestamp", () => {
  reportError({ message: "boom", stack: "at x()" }, "TestComponent");

  expect(api.post).toHaveBeenCalledWith(
    "/logs/frontend",
    expect.objectContaining({
      message: "boom",
      stack: "at x()",
      component: "TestComponent",
      url: expect.any(String),
      timestamp: expect.any(String),
    }),
  );
});

test("a failed report does not throw (would otherwise loop into another error)", () => {
  (api.post as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("network down"));
  expect(() => reportError({ message: "boom" })).not.toThrow();
});

test("installGlobalErrorLogging relays window.onerror events", () => {
  installGlobalErrorLogging();

  dispatchWindowEvent("error", { message: "uncaught boom", error: new Error("uncaught boom") });

  expect(api.post).toHaveBeenCalledWith(
    "/logs/frontend",
    expect.objectContaining({ message: "uncaught boom", component: "window.onerror" }),
  );
});

test("installGlobalErrorLogging relays unhandled promise rejections", () => {
  installGlobalErrorLogging();

  dispatchWindowEvent("unhandledrejection", { reason: new Error("rejected boom") });

  expect(api.post).toHaveBeenCalledWith(
    "/logs/frontend",
    expect.objectContaining({ message: "rejected boom", component: "unhandledrejection" }),
  );
});

test("unhandled rejection with a non-Error reason still reports a message", () => {
  installGlobalErrorLogging();

  dispatchWindowEvent("unhandledrejection", { reason: "just a string" });

  expect(api.post).toHaveBeenCalledWith(
    "/logs/frontend",
    expect.objectContaining({ message: "just a string", component: "unhandledrejection" }),
  );
});

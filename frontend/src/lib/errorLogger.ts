import { api } from "../api/client";

// Relays client-side errors to POST /logs/frontend, which writes them to
// logs/frontend/ via the backend's get_logger(). Browsers can't write local
// files directly, so this is the only way frontend errors land alongside
// every other component's logs. Spec: specs/SPEC.md "Exception Handling & Logging".
export function reportError(
  error: { message: string; stack?: string },
  component?: string,
): void {
  api
    .post("/logs/frontend", {
      message: error.message,
      stack: error.stack ?? null,
      component: component ?? null,
      url: window.location.href,
      timestamp: new Date().toISOString(),
    })
    .catch(() => {
      // Reporting failure shouldn't cascade into another error report.
    });
}

export function installGlobalErrorLogging(): void {
  window.addEventListener("error", (event) => {
    reportError({ message: event.message, stack: event.error?.stack }, "window.onerror");
  });

  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason;
    const message = reason instanceof Error ? reason.message : String(reason);
    const stack = reason instanceof Error ? reason.stack : undefined;
    reportError({ message, stack }, "unhandledrejection");
  });
}

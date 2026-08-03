import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import ErrorBoundary from "./components/shared/ErrorBoundary";
import "./index.css";
import { installGlobalErrorLogging } from "./lib/errorLogger";

installGlobalErrorLogging();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // App-wide no-polling model (see SPEC.md "UI Data Refresh: Manual Pull")
      refetchInterval: false,
      refetchOnWindowFocus: false,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
);

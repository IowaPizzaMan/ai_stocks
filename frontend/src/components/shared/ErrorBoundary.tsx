import { Component, type ErrorInfo, type ReactNode } from "react";
import { reportError } from "../../lib/errorLogger";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

// React only supports error boundaries as class components (no hook
// equivalent for componentDidCatch/getDerivedStateFromError). Reports render
// errors via errorLogger.ts so they land in logs/frontend/ alongside window-level
// errors caught by installGlobalErrorLogging(). Spec: specs/SPEC.md
// "Exception Handling & Logging".
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    reportError({ message: error.message, stack: info.componentStack ?? error.stack }, "ErrorBoundary");
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-zinc-950 text-zinc-100">
          <div className="max-w-md rounded-xl border border-zinc-800 bg-zinc-900 p-6 text-center">
            <p className="mb-2 text-lg font-semibold">Something went wrong</p>
            <p className="text-sm text-zinc-400">
              The error has been logged. Try refreshing the page.
            </p>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

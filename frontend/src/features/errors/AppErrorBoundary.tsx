import { Component, type ErrorInfo, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { ErrorFallbackPage } from "./ErrorFallbackPage";

type BoundaryProps = {
  children: ReactNode;
  resetKey: string;
};

type BoundaryState = {
  hasError: boolean;
};

/**
 * Catches render errors. Never surfaces message/stack to the user —
 * generic Persian copy only. Logs to console in development.
 */
export class AppErrorBoundary extends Component<BoundaryProps, BoundaryState> {
  state: BoundaryState = { hasError: false };

  static getDerivedStateFromError(): BoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    if (import.meta.env.DEV) {
      console.error("AppErrorBoundary caught", error, info.componentStack);
    }
  }

  componentDidUpdate(prevProps: BoundaryProps): void {
    if (prevProps.resetKey !== this.props.resetKey && this.state.hasError) {
      this.setState({ hasError: false });
    }
  }

  private handleReset = (): void => {
    this.setState({ hasError: false });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return <ErrorFallbackPage onReset={this.handleReset} />;
    }
    return this.props.children;
  }
}

/** Wraps children and resets the boundary whenever the route location changes. */
export function RouteErrorBoundary({ children }: { children: ReactNode }) {
  const location = useLocation();
  const resetKey = `${location.pathname}${location.search}${location.hash}`;
  return <AppErrorBoundary resetKey={resetKey}>{children}</AppErrorBoundary>;
}

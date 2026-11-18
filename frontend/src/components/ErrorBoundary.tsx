import { Component, type ErrorInfo, type ReactNode } from "react";
import { logger } from "../lib/logger";

interface State {
  failed: boolean;
}

/** Catches render errors anywhere below it and shows a calm, useful page instead of a blank one. */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    logger.error("Unhandled UI error", { message: error.message, stack: info.componentStack });
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="error-page">
        <div className="error-page-inner">
          <p className="eyebrow">Something broke on this page</p>
          <h1>We couldn&apos;t show this screen.</h1>
          <p className="lead">
            Nothing was posted to GitHub and your summaries are safe. Reloading usually fixes it.
          </p>
          <div className="actions">
            <button className="btn btn-primary" onClick={() => window.location.reload()}>
              Reload the page
            </button>
            <a className="link-arrow" href="/dashboard">
              Go to the dashboard
            </a>
          </div>
        </div>
      </main>
    );
  }
}

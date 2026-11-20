import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "@fontsource-variable/geist";
import "@fontsource-variable/jetbrains-mono";
import "@fontsource/instrument-serif/400.css";
import "./design/tokens.css";
import "./styles.css";
import { AppRoutes } from "./AppRoutes";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ToastProvider } from "./components/Toast";
import { DiffStoreProvider } from "./diffStore";
import { SessionProvider } from "./session";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <SessionProvider>
          <ToastProvider>
            <DiffStoreProvider>
              <AppRoutes />
            </DiffStoreProvider>
          </ToastProvider>
        </SessionProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>,
);

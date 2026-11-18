import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./styles.css";
import { AppRoutes } from "./AppRoutes";
import { DiffStoreProvider } from "./diffStore";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <DiffStoreProvider>
        <AppRoutes />
      </DiffStoreProvider>
    </BrowserRouter>
  </React.StrictMode>,
);

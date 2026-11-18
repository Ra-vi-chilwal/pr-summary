/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The browser only talks to /api on this origin; Vite forwards it to FastAPI.
// No keys or secrets ever live in the frontend.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": process.env.API_PROXY_TARGET ?? "http://localhost:8000" },
  },
  test: { environment: "jsdom" },
});

/// <reference types="vitest" />
import { copyFileSync, mkdirSync } from "node:fs";
import { join, resolve } from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

// Static hosts (Vercel) only serve files that exist, so opening /login directly gave a 404.
// Copy index.html to each page's folder, and to 404.html as the fallback for /review/<id>
// and anything else. React Router then renders the right page.
export const SPA_PAGES = ["login", "signup", "dashboard", "try", "forgot-password", "review", "get-started"];

function spaFallback(): Plugin {
  let outDir = "dist";
  return {
    name: "spa-fallback",
    apply: "build",
    configResolved(cfg) {
      outDir = resolve(cfg.root, cfg.build.outDir);
    },
    closeBundle() {
      const index = join(outDir, "index.html");
      for (const page of SPA_PAGES) {
        mkdirSync(join(outDir, page), { recursive: true });
        copyFileSync(index, join(outDir, page, "index.html"));
      }
      copyFileSync(index, join(outDir, "404.html"));
    },
  };
}

// The browser only talks to /api on this origin; Vite forwards it to FastAPI.
// No keys or secrets ever live in the frontend.
export default defineConfig({
  plugins: [react(), spaFallback()],
  server: {
    port: 5173,
    // xfwd passes the browser's IP on, so per-IP rate limits work behind the proxy.
    proxy: { "/api": { target: process.env.API_PROXY_TARGET ?? "http://localhost:8000", xfwd: true } },
  },
  test: { environment: "jsdom" },
});

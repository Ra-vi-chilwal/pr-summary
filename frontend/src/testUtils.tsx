import { render } from "@testing-library/react";
import { vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import type { Me } from "./api";
import { AppRoutes } from "./AppRoutes";
import { ToastProvider } from "./components/Toast";
import { DiffStoreProvider } from "./diffStore";
import { SessionProvider } from "./session";

export const SIGNED_OUT: Me = {
  user: null,
  installations: [],
  github_app_configured: true,
  github_login_configured: true,
};

export const SIGNED_IN: Me = {
  ...SIGNED_OUT,
  user: { id: 1, name: "Ravi Chilwal", email: "ravi@example.com", avatar_url: null, github_login: null },
};

export function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <SessionProvider>
        <ToastProvider>
          <DiffStoreProvider>
            <AppRoutes />
          </DiffStoreProvider>
        </ToastProvider>
      </SessionProvider>
    </MemoryRouter>,
  );
}

type Reply = object | Error | { status: number; body: object };
const isStatus = (r: Reply): r is { status: number; body: object } =>
  typeof r === "object" && r !== null && "status" in r && "body" in r && typeof r.status === "number";

/**
 * Fake backend. Keys are "METHOD /path" (exact path, query ignored). Each value is one reply
 * or a list of replies used in order (the last one repeats). Error = network failure.
 * GET /api/auth/me defaults to signed out.
 */
export function mockApi(routes: Record<string, Reply | Reply[]> = {}) {
  const queues = new Map<string, Reply[]>();
  for (const [k, v] of Object.entries({ "GET /api/auth/me": SIGNED_OUT, ...routes })) {
    queues.set(k, Array.isArray(v) ? [...v] : [v]);
  }
  const fn = vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${url.split("?")[0]}`;
    const q = queues.get(key);
    if (!q) throw new Error(`No mock for ${key}`);
    const reply = q.length > 1 ? q.shift()! : q[0];
    if (reply instanceof Error) throw reply;
    if (isStatus(reply)) return { ok: reply.status < 400, status: reply.status, json: async () => reply.body };
    return { ok: true, status: 200, json: async () => reply };
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

/** Calls made to one route, with parsed JSON bodies. */
export function callsTo(fn: ReturnType<typeof mockApi>, key: string) {
  return fn.mock.calls
    .filter(([url, init]) => `${(init as RequestInit | undefined)?.method ?? "GET"} ${String(url).split("?")[0]}` === key)
    .map(([, init]) => {
      const body = (init as RequestInit | undefined)?.body;
      return body ? JSON.parse(String(body)) : undefined;
    });
}

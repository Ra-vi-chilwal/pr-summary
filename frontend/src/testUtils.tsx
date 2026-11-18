import { render } from "@testing-library/react";
import { vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { AppRoutes } from "./AppRoutes";
import { DiffStoreProvider } from "./diffStore";

export function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <DiffStoreProvider>
        <AppRoutes />
      </DiffStoreProvider>
    </MemoryRouter>,
  );
}

/** Each entry answers one fetch call, in order. An Error means a network failure. */
export function mockFetch(...responses: (object | Error)[]) {
  const fn = vi.fn();
  for (const r of responses) {
    if (r instanceof Error) fn.mockRejectedValueOnce(r);
    else fn.mockResolvedValueOnce({ ok: true, json: async () => r });
  }
  vi.stubGlobal("fetch", fn);
  return fn;
}

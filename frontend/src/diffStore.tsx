import { type ReactNode, createContext, useContext, useRef } from "react";

/**
 * Pasted diffs live only in this browser tab's memory, keyed by run id, so the Review
 * screen can show them. They are never sent anywhere except the one summary request,
 * never stored on the server, and gone when the tab reloads.
 */
interface DiffStore {
  get(runId: number): string | undefined;
  set(runId: number, diff: string): void;
}

const Ctx = createContext<DiffStore | null>(null);

export function DiffStoreProvider({ children }: { children: ReactNode }) {
  const map = useRef(new Map<number, string>());
  const store = useRef<DiffStore>({
    get: (id) => map.current.get(id),
    set: (id, diff) => void map.current.set(id, diff),
  });
  return <Ctx.Provider value={store.current}>{children}</Ctx.Provider>;
}

export function useDiffStore(): DiffStore {
  const store = useContext(Ctx);
  if (!store) throw new Error("useDiffStore needs DiffStoreProvider");
  return store;
}

import { type ReactNode, createContext, useCallback, useContext, useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { type Me, getMe, logout as apiLogout } from "./api";
import { logger } from "./lib/logger";

interface Session {
  loading: boolean;
  me: Me;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const SIGNED_OUT: Me = {
  user: null,
  installations: [],
  github_app_configured: false,
  github_login_configured: false,
};

const Ctx = createContext<Session>({
  loading: true,
  me: SIGNED_OUT,
  refresh: async () => {},
  logout: async () => {},
});

export function SessionProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [me, setMe] = useState<Me>(SIGNED_OUT);

  const refresh = useCallback(async () => {
    try {
      setMe(await getMe());
    } catch (e) {
      logger.warn("Could not load session", { error: String(e) });
      setMe(SIGNED_OUT);
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } finally {
      setMe(SIGNED_OUT);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return <Ctx.Provider value={{ loading, me, refresh, logout }}>{children}</Ctx.Provider>;
}

export function useSession() {
  return useContext(Ctx);
}

/** Sends signed-out visitors to /login and brings them back afterwards. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { loading, me } = useSession();
  const location = useLocation();
  if (loading) return null;
  if (!me.user) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  return <>{children}</>;
}

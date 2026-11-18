import { Navigate, Route, Routes, useSearchParams } from "react-router-dom";
import { Shell } from "./Shell";
import { TryDiff } from "./TryDiff";
import { ForgotPassword, Login, Signup } from "./pages/Auth";
import { Dashboard } from "./pages/Dashboard";
import { GetStarted } from "./pages/GetStarted";
import { Review } from "./pages/Review";
import { RequireAuth, useSession } from "./session";

/** Signed-in visitors skip the login/signup pages. */
function GuestOnly({ children }: { children: React.ReactNode }) {
  const { loading, me } = useSession();
  const [params] = useSearchParams();
  if (loading) return null;
  if (me.user) {
    const next = params.get("next") ?? "";
    return <Navigate to={next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard"} replace />;
  }
  return <>{children}</>;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <GuestOnly>
            <Login />
          </GuestOnly>
        }
      />
      <Route
        path="/signup"
        element={
          <GuestOnly>
            <Signup />
          </GuestOnly>
        }
      />
      <Route element={<Shell />}>
        <Route path="/" element={<GetStarted />} />
        <Route
          path="/dashboard"
          element={
            <RequireAuth>
              <Dashboard />
            </RequireAuth>
          }
        />
        <Route
          path="/review/:runId"
          element={
            <RequireAuth>
              <Review />
            </RequireAuth>
          }
        />
        <Route path="/try" element={<TryDiff />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="*" element={<GetStarted />} />
      </Route>
    </Routes>
  );
}

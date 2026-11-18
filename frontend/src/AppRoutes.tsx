import { Route, Routes } from "react-router-dom";
import { Shell } from "./Shell";
import { TryDiff } from "./TryDiff";
import { Dashboard } from "./pages/Dashboard";
import { GetStarted } from "./pages/GetStarted";
import { Review } from "./pages/Review";
import { RequireAuth } from "./session";

export function AppRoutes() {
  return (
    <Routes>
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
        <Route path="*" element={<GetStarted />} />
      </Route>
    </Routes>
  );
}

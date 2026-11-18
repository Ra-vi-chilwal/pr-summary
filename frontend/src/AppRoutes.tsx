import { Route, Routes } from "react-router-dom";
import { Shell } from "./Shell";
import { TryDiff } from "./TryDiff";
import { Dashboard } from "./pages/Dashboard";
import { GetStarted } from "./pages/GetStarted";
import { Review } from "./pages/Review";

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route path="/" element={<GetStarted />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/review/:runId" element={<Review />} />
        <Route path="/try" element={<TryDiff />} />
        <Route path="*" element={<GetStarted />} />
      </Route>
    </Routes>
  );
}

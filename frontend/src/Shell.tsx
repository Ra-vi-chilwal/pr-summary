import { NavLink, Outlet } from "react-router-dom";

export function Shell() {
  return (
    <div className="shell">
      <aside className="sb" aria-label="Navigation">
        <div className="sb-top">
          <NavLink to="/" className="brand">
            PR Summary
          </NavLink>
          <p className="sb-repo mono">No repo connected</p>
          <nav>
            <NavLink to="/" end className="side-item">
              Get started
            </NavLink>
            <NavLink to="/dashboard" className="side-item">
              Dashboard
            </NavLink>
            <NavLink to="/try" className="side-item">
              Try a diff <span className="chip">Dev</span>
            </NavLink>
          </nav>
        </div>
        <div className="sb-user">
          <span>Not signed in</span>
          <span className="meta">GitHub sign-in comes with the GitHub App</span>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}

import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Icon } from "./components/Icon";
import { plural } from "./api";
import { useSession } from "./session";

export function Shell() {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]); // close the drawer after navigating

  return (
    <div className="app">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="topbar">
        <Brand />
        <button
          className="btn btn-quiet"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          aria-controls="sidebar"
          onClick={() => setOpen((o) => !o)}
        >
          <Icon name={open ? "close" : "menu"} />
        </button>
      </header>
      <button
        className="drawer-scrim"
        data-open={open}
        aria-hidden="true"
        tabIndex={-1}
        onClick={() => setOpen(false)}
      />
      <aside id="sidebar" className="sidebar" data-open={open} aria-label="Main">
        <div className="sidebar-head">
          <Brand />
          <Connection />
        </div>
        <nav className="nav">
          <NavLink to="/" end className="nav-link">
            Get started
          </NavLink>
          <NavLink to="/dashboard" className="nav-link">
            Dashboard
          </NavLink>
          <NavLink to="/try" className="nav-link">
            Try a diff
          </NavLink>
        </nav>
        <div className="sidebar-foot">
          <Account />
        </div>
      </aside>
      <main id="main" className="main" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  );
}

function Brand() {
  return (
    <Link to="/" className="brand">
      <span className="brand-mark" aria-hidden="true">
        PR
      </span>
      PR Summary
    </Link>
  );
}

function Connection() {
  const { loading, me } = useSession();
  if (loading) return <div className="connection" aria-hidden="true" />;

  const inst = me.installations[0];
  if (!inst) {
    return (
      <div className="connection">
        <span className="connection-row muted">
          <span>
            <span className="status-dot" /> No GitHub account connected
          </span>
        </span>
        {me.user && me.github_app_configured && (
          <a className="link-arrow small" href="/api/github/install">
            Connect GitHub →
          </a>
        )}
      </div>
    );
  }
  const repos = me.installations.reduce((n, i) => n + (i.repo_count ?? 0), 0);
  return (
    <div className="connection">
      <span className="connection-row">
        <span>
          <span className="status-dot on" /> <span className="mono">{inst.account_login}</span>
        </span>
        <a className="small" href={inst.manage_url} target="_blank" rel="noreferrer">
          Manage
        </a>
      </span>
      <span className="muted">{plural(repos, "repository", "repositories")} connected</span>
    </div>
  );
}

function Account() {
  const { loading, me, logout } = useSession();
  const navigate = useNavigate();
  if (loading) return null;

  if (!me.user) {
    return (
      <div className="account">
        <div className="account-text">
          <span className="account-name">Not signed in</span>
          <span className="small muted">Sign in to keep your summaries.</span>
        </div>
        <Link className="btn" to="/login">
          Sign in
        </Link>
      </div>
    );
  }
  const u = me.user;
  return (
    <div className="account">
      {u.avatar_url ? (
        <img className="avatar" src={u.avatar_url} alt="" />
      ) : (
        <span className="avatar" aria-hidden="true">
          {initials(u.name)}
        </span>
      )}
      <div className="account-text">
        <span className="account-name">{u.name}</span>
        <span className="small muted mono">{u.github_login ? `@${u.github_login}` : u.email}</span>
      </div>
      <button
        className="btn btn-quiet small"
        onClick={async () => {
          await logout();
          navigate("/login");
        }}
      >
        Log out
      </button>
    </div>
  );
}

function initials(name: string): string {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((p) => p[0]!.toUpperCase())
      .join("") || "?"
  );
}

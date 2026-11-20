import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  ApiError,
  type PullRequest,
  type Repo,
  type RunInfo,
  type RunList,
  listPulls,
  listRepos,
  listRuns,
  plural,
  summarizePull,
  timeAgo,
} from "../api";
import { Icon } from "../components/Icon";
import { RowSkeletons } from "../components/Skeleton";
import { useDiffStore } from "../diffStore";
import { useSession } from "../session";
import { reviewPath } from "./Review";

type Load<T> = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ok"; data: T };

const REVIEWS_PER_REPO = 50;

const GITHUB_NOTICES: Record<string, { kind: "ok" | "error" | "warn"; text: string }> = {
  connected: { kind: "ok", text: "GitHub is connected. Pick a repository below to see its pull requests." },
  not_yours: {
    kind: "error",
    text: "That installation belongs to a GitHub account you can't access, so we didn't connect it.",
  },
  unconfigured: { kind: "warn", text: "The GitHub App isn't configured on this server yet. See the README." },
  none_found: {
    kind: "warn",
    text: "GitHub doesn't show the PR Summary app installed on any account you can access. Use Connect GitHub to install it.",
  },
  linked_elsewhere: {
    kind: "error",
    text: "The app is installed, but that installation is already connected to a different PR Summary account. Sign in with that account, or uninstall the app on GitHub and connect again.",
  },
  link_failed: {
    kind: "error",
    text: "GitHub sign-in didn't finish, so nothing was linked. Try “Link it” again.",
  },
};

export function Dashboard() {
  const { me } = useSession();
  const [params] = useSearchParams();
  const notice = GITHUB_NOTICES[params.get("github") ?? ""];
  const [runs, setRuns] = useState<Load<RunList>>({ kind: "loading" });

  const loadRuns = useCallback(() => {
    setRuns({ kind: "loading" });
    listRuns()
      .then((data) => setRuns({ kind: "ok", data }))
      .catch(() => setRuns({ kind: "error", message: "Couldn't load your summaries. Your PRs are fine." }));
  }, []);
  useEffect(loadRuns, [loadRuns]);

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Dashboard</h1>
          <p className="lead">Pick a pull request to summarize, or reopen one you already have.</p>
        </div>
        {runs.kind === "ok" && <Usage data={runs.data} />}
      </header>

      {notice && (
        <div className={`notice ${notice.kind}`} role="status" style={{ marginBottom: "var(--space-8)" }}>
          <p>{notice.text}</p>
        </div>
      )}

      <section className="section" aria-labelledby="repos">
        <div className="section-head">
          <h2 id="repos">Repositories</h2>
          {me.installations[0] && (
            <a className="small" href={me.installations[0].manage_url} target="_blank" rel="noreferrer">
              Change repository access <Icon name="external" />
            </a>
          )}
        </div>
        {me.installations.length === 0 ? <ConnectEmpty configured={me.github_app_configured} /> : <Repos />}
      </section>

      <section className="section" aria-labelledby="recent">
        <div className="section-head">
          <h2 id="recent">Recent summaries</h2>
        </div>
        {runs.kind === "loading" && <RowSkeletons />}
        {runs.kind === "error" && (
          <div className="notice error" role="alert">
            <p>{runs.message}</p>
            <button className="btn" onClick={loadRuns}>
              Try again
            </button>
          </div>
        )}
        {runs.kind === "ok" && runs.data.runs.length === 0 && (
          <div className="empty">
            <h3>No summaries yet</h3>
            <p className="muted">
              Pick a pull request above, or paste a public PR link on <Link to="/try">Try a diff</Link>.
              Every summary you make shows up here.
            </p>
          </div>
        )}
        {runs.kind === "ok" && runs.data.runs.length > 0 && (
          <ul className="rows">
            {runs.data.runs.map((r) => (
              <RunRow key={r.id} run={r} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Usage({ data }: { data: RunList }) {
  const pct = Math.min(100, (data.spend_this_month_usd / data.spend_cap_usd) * 100);
  return (
    <div className="stats" aria-label="Usage this month">
      <div className="stat">
        <span className="eyebrow">Summaries this month</span>
        <span className="stat-value">{data.runs_this_month}</span>
        <span className="small muted">Limit {REVIEWS_PER_REPO} per repository</span>
      </div>
      <div className="stat">
        <span className="eyebrow">AI spend</span>
        <span className="stat-value">
          ${data.spend_this_month_usd.toFixed(2)}{" "}
          <span className="small muted">of ${data.spend_cap_usd.toFixed(0)}</span>
        </span>
        <span className="meter" role="img" aria-label={`${pct.toFixed(0)}% of the monthly cap used`}>
          <span style={{ width: `${pct}%` }} />
        </span>
      </div>
    </div>
  );
}

const STATUS: Record<string, { text: string; dot: string }> = {
  done: { text: "Summary ready", dot: "on" },
  skipped: { text: "Skipped", dot: "" },
  failed: { text: "Failed, nothing posted", dot: "bad" },
  capped: { text: "Stopped at spend limit", dot: "warn" },
  running: { text: "Running", dot: "warn" },
};

function RunRow({ run }: { run: RunInfo }) {
  const s = STATUS[run.status] ?? { text: run.status, dot: "" };
  const where = run.repo ? `${run.repo}${run.pr_number ? ` #${run.pr_number}` : ""}` : `#${run.id}`;
  const body = (
    <>
      <span className={`status-dot ${s.dot}`} aria-hidden="true" />
      <span style={{ minWidth: 0 }}>
        <span className="row-title" style={{ display: "block" }}>
          {run.title || "Untitled diff"}
        </span>
        <span className="row-meta">
          <span className="mono">{where}</span> · {plural(run.files_total, "file")} ·{" "}
          {timeAgo(run.created_at)}
        </span>
      </span>
      <span className={`row-side ${run.status === "failed" ? "bad" : ""}`}>
        {run.summary_id !== null ? "View summary →" : s.text}
      </span>
    </>
  );
  return (
    <li>
      {run.summary_id !== null ? (
        <Link className="row" to={reviewPath(run.id)} aria-label={`View summary: ${run.title || "Untitled diff"}`}>
          {body}
        </Link>
      ) : (
        <div className="row" title={run.message}>
          {body}
        </div>
      )}
    </li>
  );
}

function ConnectEmpty({ configured }: { configured: boolean }) {
  return (
    <div className="empty">
      <h3>Connect GitHub to summarize your pull requests</h3>
      <p className="muted">
        Install the PR Summary app on the repositories you choose, private ones included. It can
        read pull requests and write one comment; it can&apos;t approve, merge or push.
      </p>
      {configured ? (
        <>
          <a className="btn btn-primary" href="/api/github/install">
            Connect GitHub
          </a>
          <p className="small muted">
            Already installed the app on GitHub, but it isn&apos;t showing here?{" "}
            <a href="/api/github/link">Link it</a>
          </p>
        </>
      ) : (
        <p className="small muted">
          The GitHub App isn&apos;t configured on this server yet. Follow “Create the GitHub App” in
          the README, then restart the backend.
        </p>
      )}
    </div>
  );
}

function Repos() {
  const [repos, setRepos] = useState<Load<Repo[]>>({ kind: "loading" });
  const [selected, setSelected] = useState<Repo | null>(null);

  const load = useCallback(() => {
    setRepos({ kind: "loading" });
    listRepos()
      .then((d) => setRepos({ kind: "ok", data: d.repos }))
      .catch((e) =>
        setRepos({
          kind: "error",
          message: e instanceof ApiError && e.detail ? e.detail : "Couldn't load your repositories.",
        }),
      );
  }, []);
  useEffect(load, [load]);

  if (repos.kind === "loading") return <RowSkeletons count={3} />;
  if (repos.kind === "error")
    return (
      <div className="notice error" role="alert">
        <p>{repos.message}</p>
        <button className="btn" onClick={load}>
          Try again
        </button>
      </div>
    );
  if (repos.data.length === 0)
    return (
      <div className="empty">
        <h3>The app can&apos;t see any repositories</h3>
        <p className="muted">Give it access to at least one repository in the installation settings.</p>
      </div>
    );
  if (selected) return <Pulls repo={selected} onBack={() => setSelected(null)} />;

  return (
    <ul className="rows">
      {repos.data.map((r) => (
        <li key={r.full_name}>
          <button className="row" onClick={() => setSelected(r)}>
            <span className="status-dot on" aria-hidden="true" />
            <span style={{ minWidth: 0 }}>
              <span className="row-title mono" style={{ display: "block" }}>
                {r.full_name}
              </span>
              {r.updated_at && <span className="row-meta">Updated {timeAgo(r.updated_at)}</span>}
            </span>
            <span className="row-side">
              {r.private && (
                <span className="badge">
                  <Icon name="lock" /> Private
                </span>
              )}{" "}
              Open PRs →
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

function Pulls({ repo, onBack }: { repo: Repo; onBack: () => void }) {
  const [pulls, setPulls] = useState<Load<PullRequest[]>>({ kind: "loading" });
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const diffStore = useDiffStore();

  useEffect(() => {
    listPulls(repo.owner, repo.name)
      .then((d) => setPulls({ kind: "ok", data: d.pulls }))
      .catch((e) =>
        setPulls({
          kind: "error",
          message: e instanceof ApiError && e.detail ? e.detail : "Couldn't load pull requests.",
        }),
      );
  }, [repo]);

  async function run(pr: PullRequest) {
    setBusy(pr.number);
    setError(null);
    try {
      const result = await summarizePull(repo.owner, repo.name, pr.number);
      if (result.diff) diffStore.set(result.run_id, result.diff);
      if (result.status === "done") navigate(reviewPath(result.run_id));
      else setError(result.message);
    } catch (e) {
      setError(e instanceof ApiError && e.detail ? e.detail : "Couldn't summarize this PR. Nothing was posted.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <p className="crumbs">
        <button className="path-button" onClick={onBack}>
          All repositories
        </button>{" "}
        / <span className="mono">{repo.full_name}</span>
      </p>
      {error && (
        <div className="notice error" role="alert" style={{ marginBottom: "var(--space-4)" }}>
          <p>{error}</p>
        </div>
      )}
      {pulls.kind === "loading" && <RowSkeletons count={3} />}
      {pulls.kind === "error" && (
        <div className="notice error" role="alert">
          <p>{pulls.message}</p>
        </div>
      )}
      {pulls.kind === "ok" && pulls.data.length === 0 && (
        <div className="empty">
          <h3>No open pull requests</h3>
          <p className="muted">When someone opens one in {repo.name}, it will show up here.</p>
        </div>
      )}
      {pulls.kind === "ok" && pulls.data.length > 0 && (
        <ul className="rows">
          {pulls.data.map((pr) => (
            <li key={pr.number}>
              <button className="row" onClick={() => run(pr)} disabled={busy !== null}>
                <span className="mono small muted">#{pr.number}</span>
                <span style={{ minWidth: 0 }}>
                  <span className="row-title" style={{ display: "block" }}>
                    {pr.title}
                  </span>
                  <span className="row-meta">
                    {pr.author ? `@${pr.author} · ` : ""}updated {timeAgo(pr.updated_at)}
                    {pr.draft ? " · draft" : ""}
                  </span>
                </span>
                <span className="row-side">{busy === pr.number ? "Reading the PR…" : "Summarize →"}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

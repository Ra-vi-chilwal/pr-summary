import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { type RunInfo, type RunList, listRuns, timeAgo } from "../api";

type State = { kind: "loading" } | { kind: "error" } | { kind: "ok"; data: RunList };

const STATUS_TEXT: Record<string, string> = {
  done: "Summary ready",
  skipped: "Skipped",
  failed: "Failed, nothing posted",
  capped: "Stopped: spend limit",
  running: "Running",
};

export function Dashboard() {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback(() => {
    setState({ kind: "loading" });
    listRuns()
      .then((data) => setState({ kind: "ok", data }))
      .catch(() => setState({ kind: "error" }));
  }, []);

  useEffect(load, [load]);

  return (
    <div className="page">
      <div className="dash-head">
        <div>
          <h1>Dashboard</h1>
          <p className="meta">Pull requests reviewed. Newest first.</p>
        </div>
        {state.kind === "ok" && (
          <p className="meta">
            {state.data.runs_this_month} runs this month · AI spend $
            {state.data.spend_this_month_usd.toFixed(2)} of ${state.data.spend_cap_usd.toFixed(0)}
          </p>
        )}
      </div>

      {state.kind === "loading" && <div className="state-box">Loading PRs...</div>}
      {state.kind === "error" && (
        <div className="state-box">
          <p className="error-text">Couldn&apos;t load. Your PRs are fine.</p>
          <button onClick={load}>Try again</button>
        </div>
      )}
      {state.kind === "ok" && state.data.runs.length === 0 && (
        <div className="state-box">
          <p>No PRs reviewed yet.</p>
          <p className="meta">
            <Link to="/try">Try it on a diff</Link> to see your first summary here.
          </p>
        </div>
      )}
      {state.kind === "ok" && state.data.runs.length > 0 && (
        <ul className="runs">
          {state.data.runs.map((r) => (
            <RunRow key={r.id} run={r} />
          ))}
        </ul>
      )}
    </div>
  );
}

function RunRow({ run }: { run: RunInfo }) {
  const failed = run.status === "failed";
  return (
    <li className="run">
      <div className="run-title">{run.title || "Untitled diff"}</div>
      <div className="run-side">
        <span className={`status ${failed ? "failed" : ""}`}>{STATUS_TEXT[run.status] ?? run.status}</span>
        {run.summary_id !== null ? (
          <Link to={`/review/${run.id}`}>View summary</Link>
        ) : (
          <span className="meta">{failed ? "Not shown on GitHub" : run.message}</span>
        )}
      </div>
      <div className="run-meta meta">
        <span className="mono">#{run.id}</span> · {run.files_total} {run.files_total === 1 ? "file" : "files"} ·{" "}
        {timeAgo(run.created_at)}
      </div>
    </li>
  );
}

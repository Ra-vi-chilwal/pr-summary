import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { type RunDetail, UNSURE_NOTE, getRun, timeAgo } from "../api";
import { type DiffFile, type Row, parseDiffFiles } from "../diffView";
import { useDiffStore } from "../diffStore";

type State = { kind: "loading" } | { kind: "error" } | { kind: "ok"; data: RunDetail };

export function Review() {
  const runId = Number(useParams().runId);
  const diffStore = useDiffStore();
  const [state, setState] = useState<State>({ kind: "loading" });
  const [view, setView] = useState<string>("overview"); // "overview" or a file path

  const load = useCallback(() => {
    setState({ kind: "loading" });
    getRun(runId)
      .then((data) => setState({ kind: "ok", data }))
      .catch(() => setState({ kind: "error" }));
  }, [runId]);
  useEffect(load, [load]);

  const diffText = diffStore.get(runId);
  const diffFiles = useMemo(() => (diffText ? parseDiffFiles(diffText) : []), [diffText]);

  if (state.kind === "loading") return <Message>Loading this review...</Message>;
  if (state.kind === "error")
    return (
      <Message>
        <p className="error-text">Couldn&apos;t load this review.</p>
        <button onClick={load}>Try again</button>
      </Message>
    );

  const { run, result, comment_markdown } = state.data;
  if (!result || !comment_markdown) return <Message title={run.title}>{run.message || "Nothing to summarize."}</Message>;

  const checkFirst = new Map(result.check_first.map((c, i) => [c.path, i + 1]));
  const note = result.files.find((f) => f.path === view);
  const diffFile = diffFiles.find((f) => f.path === view);

  return (
    <div className="rv">
      <div className="rv-head">
        <div>
          <h1>{run.title || "Untitled diff"}</h1>
          <p className="meta">
            <span className="mono">#{run.id}</span> · {run.files_kept} of {run.files_total} files read ·{" "}
            {timeAgo(run.created_at)}
          </p>
        </div>
        <CopyButton text={comment_markdown} />
      </div>
      <div className="rv-body">
        <nav className="rv-side" aria-label="Files">
          <p className="side-label">This pull request</p>
          <button className="side-item" aria-current={view === "overview"} onClick={() => setView("overview")}>
            Overview
          </button>
          <p className="side-label">Check these first</p>
          {result.check_first.map((c, i) => (
            <button key={c.path} className="side-item file-item" aria-current={view === c.path} onClick={() => setView(c.path)}>
              <span className="num">{i + 1}</span>
              <span className="mono">{c.path}</span>
            </button>
          ))}
          {result.check_first.length === 0 && <p className="meta side-pad">None picked.</p>}
          <p className="side-label">All files ({result.files.length})</p>
          {result.files.map((f) => (
            <button key={f.path} className="side-item mono" aria-current={view === f.path} onClick={() => setView(f.path)}>
              {f.path}
            </button>
          ))}
        </nav>

        <div className="rv-main">
          {view === "overview" ? (
            <div className="rv-pad">
              <Overview data={state.data} onOpen={setView} />
            </div>
          ) : (
            <section>
              <div className="file-head">
                <span className="name mono">{view}</span>
                {diffFile && (
                  <span className="delta">
                    <span className="del">−{diffFile.deletions}</span> <span className="add">+{diffFile.additions}</span>
                  </span>
                )}
              </div>
              {checkFirst.has(view) && (
                <div className="note-card">
                  <b>Check first.</b> {result.check_first.find((c) => c.path === view)?.reason}
                </div>
              )}
              {note && (
                <div className="note-card">
                  <b>AI note.</b> {note.unsure ? `${UNSURE_NOTE} ${note.note}`.trim() : note.note}
                  <span className="meta"> Written by AI. It can be wrong.</span>
                </div>
              )}
              {diffFile ? (
                <DiffTable file={diffFile} />
              ) : (
                <p className="rv-pad meta">
                  The diff isn&apos;t stored. We only keep the summary. To see the code here, paste the
                  diff again on <Link to="/try">Try a diff</Link>.
                </p>
              )}
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

function Overview({ data, onOpen }: { data: RunDetail; onOpen: (path: string) => void }) {
  const result = data.result!;
  return (
    <div className="comment">
      <div className="bar">
        <span>How the reviewer will see it on GitHub</span>
        <span>One comment, edited on new commits</span>
      </div>
      <div className="body">
        <div className="section">
          <h2>What changed</h2>
          <p>{result.overview}</p>
        </div>
        <div className="section">
          <h2>Check these first</h2>
          {result.check_first.length === 0 ? (
            <p>Could not pick the riskiest files. Read the diff as usual.</p>
          ) : (
            <ol className="check">
              {result.check_first.map((c) => (
                <li key={c.path}>
                  <button className="link-btn mono" onClick={() => onOpen(c.path)}>
                    {c.path}
                  </button>
                  <span className="why">{c.reason}</span>
                </li>
              ))}
            </ol>
          )}
        </div>
        <div className="section">
          <h2>All files</h2>
          <div className="scroll-x">
            <table className="files">
              <thead>
                <tr>
                  <th>File</th>
                  <th>What changed</th>
                </tr>
              </thead>
              <tbody>
                {result.files.map((f) => (
                  <tr key={f.path}>
                    <td className="mono">{f.path}</td>
                    <td>{f.unsure ? `${UNSURE_NOTE} ${f.note}`.trim() : f.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <div className="ai">Written by AI. It can be wrong.</div>
    </div>
  );
}

function DiffTable({ file }: { file: DiffFile }) {
  if (file.binary) return <p className="rv-pad meta">Binary file. No diff to show.</p>;
  return (
    <div className="diff">
      <table>
        <colgroup>
          <col className="ln-col" />
          <col />
          <col className="ln-col" />
          <col />
        </colgroup>
        <tbody>
          {file.rows.map((row, i) => (
            <DiffRow key={i} row={row} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DiffRow({ row }: { row: Row }) {
  if (row.kind === "hunk")
    return (
      <tr className="gap">
        <td colSpan={4}>{row.text}</td>
      </tr>
    );
  const del = row.kind === "chg" && row.left ? "del" : "";
  const add = row.kind === "chg" && row.right ? "add" : "";
  return (
    <tr>
      <td className={`ln ${del}`}>{row.left?.n ?? ""}</td>
      <td className={del}>{row.left?.text ?? ""}</td>
      <td className={`ln ${add}`}>{row.right?.n ?? ""}</td>
      <td className={add}>{row.right?.text ?? ""}</td>
    </tr>
  );
}

function Message({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="page">
      <p className="meta">
        <Link to="/dashboard">Back to dashboard</Link>
      </p>
      {title !== undefined && <h1>{title || "Untitled diff"}</h1>}
      <div className="state-box">{children}</div>
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="primary"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
      }}
    >
      {copied ? "Copied" : "Copy comment"}
    </button>
  );
}

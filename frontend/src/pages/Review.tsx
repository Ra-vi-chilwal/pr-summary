import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { type RunDetail, type SummaryResult, UNSURE_NOTE, getRun, plural, timeAgo } from "../api";
import { Icon } from "../components/Icon";
import { Skeleton } from "../components/Skeleton";
import { useToast } from "../components/Toast";
import { type DiffFile, type Row, parseDiffFiles } from "../diffView";
import { useDiffStore } from "../diffStore";

type State = { kind: "loading" } | { kind: "error" } | { kind: "ok"; data: RunDetail };

export function Review() {
  const runId = Number(useParams().runId);
  const diffStore = useDiffStore();
  const [state, setState] = useState<State>({ kind: "loading" });
  const [view, setView] = useState<string>("overview");

  const load = useCallback(() => {
    setState({ kind: "loading" });
    getRun(runId)
      .then((data) => setState({ kind: "ok", data }))
      .catch(() => setState({ kind: "error" }));
  }, [runId]);
  useEffect(load, [load]);

  const diffText = diffStore.get(runId);
  const diffFiles = useMemo(() => (diffText ? parseDiffFiles(diffText) : []), [diffText]);

  if (state.kind === "loading") return <ReviewSkeleton />;
  if (state.kind === "error")
    return (
      <Message>
        <div className="notice error" role="alert">
          <p>Couldn&apos;t load this summary. Nothing was changed on GitHub.</p>
          <button className="btn" onClick={load}>
            Try again
          </button>
        </div>
      </Message>
    );

  const { run, result, comment_markdown, model } = state.data;
  if (!result || !comment_markdown)
    return (
      <Message title={run.title || "Untitled diff"}>
        <div className="empty">
          <h3>{run.status === "failed" ? "This run failed, so nothing was posted" : "Nothing to summarize"}</h3>
          <p className="muted">{run.message}</p>
        </div>
      </Message>
    );

  const select = (v: string) => {
    setView(v);
    document.getElementById("main")?.scrollTo?.({ top: 0 });
    window.scrollTo?.({ top: 0 });
  };
  const skipped = result.skipped ?? [];
  const where = run.repo ? `${run.repo}${run.pr_number ? ` #${run.pr_number}` : ""}` : `Run #${run.id}`;

  return (
    <article>
      <header className="review-head">
        <div style={{ minWidth: 0 }}>
          <nav className="crumbs" aria-label="Breadcrumb">
            <Link to="/dashboard">Dashboard</Link> / <span className="mono">{where}</span>
          </nav>
          <h1>{run.title || "Untitled diff"}</h1>
          <p className="review-meta">
            <span className="mono">{where}</span>
            <span>Summarized {timeAgo(run.created_at)}</span>
            {model && <span className="mono">{model}</span>}
          </p>
        </div>
        <div style={{ display: "flex", gap: "var(--space-6)", alignItems: "flex-end", flexWrap: "wrap" }}>
          <Coverage read={run.files_kept} total={run.files_total} skipped={skipped} />
          <CopyButton text={comment_markdown} />
        </div>
      </header>

      <div className="review-body">
        <nav className="filelist" aria-label="Files in this pull request">
          <button className="file-link sans" aria-current={view === "overview"} onClick={() => select("overview")}>
            Overview
          </button>
          <p className="eyebrow filelist-label">Check these first</p>
          {result.check_first.map((c, i) => (
            <button
              key={c.path}
              className={`file-link ${i === 0 ? "first" : ""}`}
              aria-current={view === c.path}
              onClick={() => select(c.path)}
            >
              <span className="n">{i + 1}</span>
              <span>{c.path}</span>
            </button>
          ))}
          {result.check_first.length === 0 && <p className="small muted filelist-label">None picked.</p>}
          <p className="eyebrow filelist-label">All files · {result.files.length}</p>
          {result.files.map((f) => (
            <button key={f.path} className="file-link" aria-current={view === f.path} onClick={() => select(f.path)}>
              {f.path}
            </button>
          ))}
        </nav>

        {view === "overview" ? (
          <Overview result={result} onOpen={select} />
        ) : (
          <FileView
            path={view}
            result={result}
            diffFile={diffFiles.find((f) => f.path === view)}
            hasDiff={Boolean(diffText)}
          />
        )}
      </div>
    </article>
  );
}

function Coverage({ read, total, skipped }: { read: number; total: number; skipped: { path: string; reason: string }[] }) {
  const pct = total ? (read / total) * 100 : 0;
  const reasons = Array.from(new Set(skipped.map((s) => s.reason)));
  return (
    <div className="coverage">
      <div className="coverage-label">
        <span>
          <strong>{read}</strong> of {plural(total, "file")} read
        </span>
      </div>
      <span className="meter" role="img" aria-label={`${read} of ${total} files read`}>
        <span style={{ width: `${pct}%` }} />
      </span>
      {skipped.length > 0 && (
        <span className="coverage-note" title={skipped.map((s) => `${s.path} (${s.reason})`).join("\n")}>
          {skipped.length === 1 ? (
            <>
              Skipped <span className="mono">{skipped[0].path}</span> ({skipped[0].reason})
            </>
          ) : (
            <>
              Skipped {skipped.length} files: {reasons.join(", ")}
            </>
          )}
        </span>
      )}
    </div>
  );
}

function Overview({ result, onOpen }: { result: SummaryResult; onOpen: (p: string) => void }) {
  return (
    <div className="doc">
      <section className="doc-section" aria-labelledby="what">
        <h2 id="what">What changed</h2>
        <p>{result.overview}</p>
      </section>

      <section className="doc-section" aria-labelledby="first">
        <h2 id="first">Check these first</h2>
        {result.check_first.length === 0 ? (
          <p className="muted">Could not pick the riskiest files. Read the diff as usual.</p>
        ) : (
          <ol className="check-list">
            {result.check_first.map((c, i) => (
              <li key={c.path} className={`check-item ${i === 0 ? "first" : ""}`}>
                <span className="check-num">{i + 1}</span>
                <button className="path-button" onClick={() => onOpen(c.path)}>
                  {c.path}
                </button>
                <span className="check-why">{c.reason}</span>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="doc-section" aria-labelledby="all">
        <h2 id="all">All files</h2>
        <div style={{ overflowX: "auto" }}>
          <table className="file-table">
            <thead>
              <tr>
                <th scope="col">File</th>
                <th scope="col">What changed</th>
              </tr>
            </thead>
            <tbody>
              {result.files.map((f) => (
                <tr key={f.path}>
                  <td>
                    <button className="path-button" onClick={() => onOpen(f.path)}>
                      {f.path}
                    </button>
                  </td>
                  <td>
                    <NoteText note={f.note} unsure={f.unsure} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <p className="ai-foot">Written by AI. It can be wrong. Use it to decide where to look, not as a verdict.</p>
    </div>
  );
}

function NoteText({ note, unsure }: { note: string; unsure: boolean }) {
  if (!unsure) return <>{note}</>;
  return (
    <span>
      <span className="unclear">{UNSURE_NOTE}</span>
      {note && note !== UNSURE_NOTE ? ` ${note}` : ""}
    </span>
  );
}

function FileView({
  path,
  result,
  diffFile,
  hasDiff,
}: {
  path: string;
  result: SummaryResult;
  diffFile: DiffFile | undefined;
  hasDiff: boolean;
}) {
  const idx = result.check_first.findIndex((c) => c.path === path);
  const note = result.files.find((f) => f.path === path);
  return (
    <section aria-label={path} style={{ minWidth: 0 }}>
      <div className="file-view-head">
        <span className="mono" style={{ fontWeight: "var(--weight-semibold)", wordBreak: "break-all" }}>
          {path}
        </span>
        {diffFile && (
          <span className="delta">
            <span className="del">−{diffFile.deletions}</span> <span className="add">+{diffFile.additions}</span>
          </span>
        )}
      </div>
      <div className="file-view-notes">
        {idx >= 0 && (
          <div className={`check-item ${idx === 0 ? "first" : ""}`}>
            <span className="check-num">{idx + 1}</span>
            <strong>Check this first</strong>
            <span className="check-why">{result.check_first[idx].reason}</span>
          </div>
        )}
        {note && (
          <p>
            <NoteText note={note.note} unsure={note.unsure} />{" "}
            <span className="small muted">Written by AI. It can be wrong.</span>
          </p>
        )}
      </div>
      {diffFile ? (
        <DiffTable file={diffFile} />
      ) : (
        <div className="file-view-notes">
          <div className="notice">
            <p className="small">
              {hasDiff
                ? "This file isn't in the diff we have in this tab."
                : "We don't store diffs, only the summary. Summarize the PR again in this tab to see the code here."}
            </p>
          </div>
        </div>
      )}
    </section>
  );
}

function DiffTable({ file }: { file: DiffFile }) {
  if (file.binary)
    return (
      <div className="file-view-notes">
        <p className="muted">Binary file. There&apos;s no text diff to show.</p>
      </div>
    );
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

function CopyButton({ text }: { text: string }) {
  const toast = useToast();
  return (
    <button
      className="btn btn-primary"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          toast("Comment copied. Paste it into the PR on GitHub.");
        } catch {
          toast("Couldn't copy. Select the text on Try a diff instead.");
        }
      }}
    >
      <Icon name="copy" /> Copy comment
    </button>
  );
}

function Message({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="page">
      <nav className="crumbs" aria-label="Breadcrumb">
        <Link to="/dashboard">Dashboard</Link>
      </nav>
      {title && <h1 style={{ marginBottom: "var(--space-6)" }}>{title}</h1>}
      {children}
    </div>
  );
}

function ReviewSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading this summary">
      <p className="visually-hidden">Loading this summary...</p>
      <div className="review-head">
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
          <Skeleton width="8rem" height="0.8em" />
          <Skeleton width="60%" height="1.6em" />
          <Skeleton width="14rem" height="0.8em" />
        </div>
        <Skeleton width="10rem" height="var(--control-height)" />
      </div>
      <div className="review-body">
        <div className="filelist" style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
          {[70, 85, 60, 90, 75, 65].map((w, i) => (
            <Skeleton key={i} width={`${w}%`} />
          ))}
        </div>
        <div className="doc">
          <div className="doc-section">
            <Skeleton width="9rem" height="1.2em" />
            <Skeleton width="95%" />
            <Skeleton width="88%" />
            <Skeleton width="60%" />
          </div>
          <div className="doc-section">
            <Skeleton width="11rem" height="1.2em" />
            {[0, 1, 2].map((i) => (
              <div key={i} className="check-item" style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                <Skeleton width="16rem" />
                <Skeleton width="80%" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

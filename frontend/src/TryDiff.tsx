import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ApiError,
  type SummarizeResult,
  type Verdict,
  countFiles,
  isPrLink,
  plural,
  saveVerdict,
  summarize,
} from "./api";
import { Icon } from "./components/Icon";
import { Skeleton } from "./components/Skeleton";
import { useToast } from "./components/Toast";
import { useDiffStore } from "./diffStore";
import { useSession } from "./session";
import { reviewPath } from "./pages/Review";

type Phase =
  | { kind: "idle" }
  | { kind: "loading"; text: string }
  | { kind: "error"; message: string | null }
  | { kind: "result"; result: SummarizeResult };

export function TryDiff() {
  const [diff, setDiff] = useState("");
  const [title, setTitle] = useState("");
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const diffStore = useDiffStore();

  async function run() {
    const link = isPrLink(diff);
    setPhase({
      kind: "loading",
      text: link ? "Getting the PR from GitHub and reading it..." : `Reading ${countFiles(diff)} files...`,
    });
    try {
      const result = await summarize(diff, title);
      // Tab memory only, for the summary page. For a link, the backend sends back the diff it read.
      diffStore.set(result.run_id, result.diff ?? diff);
      if (link && result.title) setTitle(result.title);
      setPhase({ kind: "result", result });
    } catch (e) {
      setPhase({ kind: "error", message: e instanceof ApiError ? e.detail : null });
    }
  }

  const loading = phase.kind === "loading";

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Try a diff</h1>
          <p className="lead">
            Paste a link to a pull request and get the summary we would post on it. Public repos work
            for anyone; private ones work once you&apos;ve connected GitHub.
          </p>
        </div>
      </header>

      <div className="try">
        <form
          className="try-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (!loading && diff.trim()) void run();
          }}
        >
          <div className="field">
            <label className="field-label" htmlFor="pr-input">
              PR link or diff
            </label>
            <textarea
              id="pr-input"
              className="textarea"
              rows={6}
              value={diff}
              onChange={(e) => setDiff(e.target.value)}
              placeholder="https://github.com/you/repo/pull/1"
              disabled={loading}
              spellCheck={false}
              aria-describedby="pr-hint"
            />
            <span id="pr-hint" className="field-hint">
              A link like <code>github.com/owner/repo/pull/12</code>, or the raw text of a{" "}
              <code>.diff</code>. We send code files to the AI for this summary only and never store
              the diff. Nothing is posted to GitHub from here.
            </span>
          </div>
          <div className="field" style={{ maxWidth: "32rem" }}>
            <label className="field-label" htmlFor="pr-title">
              Title <span className="muted">(optional, filled in from the PR)</span>
            </label>
            <input
              id="pr-title"
              className="input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={loading}
            />
          </div>
          <div className="actions">
            <button type="submit" className="btn btn-primary btn-lg" disabled={loading || diff.trim() === ""}>
              Summarize
            </button>
            {phase.kind === "idle" && <span className="small muted">Paste a PR link to see the summary.</span>}
          </div>
        </form>

        <section aria-live="polite">
          {phase.kind === "loading" && <LoadingResult text={phase.text} />}
          {phase.kind === "error" && (
            <div className="notice error" role="alert">
              <p>{phase.message ?? "Couldn't reach the server. Nothing was posted."}</p>
              <button className="btn" onClick={run}>
                Try again
              </button>
            </div>
          )}
          {phase.kind === "result" && <Result result={phase.result} />}
        </section>
      </div>
    </div>
  );
}

function LoadingResult({ text }: { text: string }) {
  return (
    <div className="try-result" aria-busy="true">
      <p>{text}</p>
      <div className="doc-section" aria-hidden="true">
        <Skeleton width="9rem" height="1.2em" />
        <Skeleton width="92%" />
        <Skeleton width="70%" />
      </div>
      <div className="check-list" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <div key={i} className="check-item" style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
            <Skeleton width="14rem" />
            <Skeleton width="75%" />
          </div>
        ))}
      </div>
    </div>
  );
}

function Result({ result }: { result: SummarizeResult }) {
  const { me } = useSession();
  if (result.status !== "done" || !result.comment_markdown) {
    return (
      <div className="try-result">
        <div className={`notice ${result.status === "failed" ? "error" : "warn"}`} role="status">
          <p>{result.message}</p>
          {result.skipped.length > 0 && (
            <p className="small">
              Skipped:{" "}
              {result.skipped.map((s, i) => (
                <span key={s.path}>
                  {i > 0 && ", "}
                  <code>{s.path}</code> ({s.reason})
                </span>
              ))}
            </p>
          )}
        </div>
      </div>
    );
  }
  return (
    <div className="try-result">
      <div className="section-head" style={{ marginBottom: 0 }}>
        <div>
          <h2>Comment preview</h2>
          <p className="small muted">
            Read {result.files_kept} of {plural(result.files_total, "file")}
            {result.skipped.length > 0 && ` · skipped ${result.skipped.map((s) => s.path).join(", ")}`}
          </p>
        </div>
        <div className="actions">
          {me.user ? (
            <Link className="link-arrow" to={reviewPath(result.run_id)}>
              Open full summary with the diff →
            </Link>
          ) : (
            <Link className="link-arrow" to={`/login?next=${encodeURIComponent(reviewPath(result.run_id))}`}>
              Sign in to keep this summary →
            </Link>
          )}
        </div>
      </div>
      <pre className="textarea" data-testid="comment" style={{ whiteSpace: "pre-wrap", margin: 0 }}>
        {result.comment_markdown}
      </pre>
      <p className="ai-foot" style={{ borderTop: 0, paddingTop: 0 }}>
        Written by AI. It can be wrong.
      </p>
      <div className="actions">
        <CopyButton text={result.comment_markdown} />
      </div>
      {result.summary_id !== null && <VerdictForm summaryId={result.summary_id} />}
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const toast = useToast();
  return (
    <button
      className="btn"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          toast("Comment copied.");
        } catch {
          toast("Couldn't copy. Select the text above instead.");
        }
      }}
    >
      <Icon name="copy" /> Copy comment
    </button>
  );
}

function VerdictForm({ summaryId }: { summaryId: number }) {
  const [accurate, setAccurate] = useState<Verdict["accurate"] | null>(null);
  const [savedTime, setSavedTime] = useState<boolean | null>(null);
  const [note, setNote] = useState("");
  const [state, setState] = useState<"editing" | "saving" | "saved" | "error">("editing");

  if (state === "saved")
    return (
      <div className="notice ok" role="status">
        <p>Verdict saved. Thank you.</p>
      </div>
    );

  async function submit() {
    if (!accurate) return;
    setState("saving");
    try {
      await saveVerdict(summaryId, { accurate, saved_time: savedTime, note });
      setState("saved");
    } catch {
      setState("error");
    }
  }

  return (
    <details className="verdict" open>
      <summary>Rate this summary</summary>
      <div className="verdict-body">
        <fieldset className="choices" role="radiogroup" aria-label="Accurate">
          <legend>Is it accurate?</legend>
          {(["yes", "partly", "no"] as const).map((v) => (
            <label key={v} className="choice">
              <input type="radio" name="accurate" checked={accurate === v} onChange={() => setAccurate(v)} />
              <span>{v}</span>
            </label>
          ))}
        </fieldset>
        <fieldset className="choices" role="radiogroup" aria-label="Saved time">
          <legend>Would it have saved you time on this PR?</legend>
          {[true, false].map((v) => (
            <label key={String(v)} className="choice">
              <input type="radio" name="saved" checked={savedTime === v} onChange={() => setSavedTime(v)} />
              <span>{v ? "yes" : "no"}</span>
            </label>
          ))}
        </fieldset>
        <div className="field">
          <label className="field-label" htmlFor="verdict-note">
            What was actually slow about reviewing it?
          </label>
          <textarea
            id="verdict-note"
            className="textarea"
            rows={3}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </div>
        {state === "error" && <p className="field-error">Couldn&apos;t save. Your summary is fine; try again.</p>}
        <button className="btn" onClick={submit} disabled={!accurate || state === "saving"}>
          Save verdict
        </button>
      </div>
    </details>
  );
}

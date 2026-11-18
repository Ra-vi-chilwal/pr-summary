import { useState } from "react";
import { Link } from "react-router-dom";
import { type SummarizeResult, type Verdict, countFiles, saveVerdict, summarize } from "./api";
import { useDiffStore } from "./diffStore";

const PR_LINK = /^https?:\/\/github\.com\/[^/\s]+\/[^/\s]+\/pull\/\d+/;

/** If someone pastes a PR link instead of the diff text, return the .diff link to open. */
export function diffLinkFor(text: string): string | null {
  const match = PR_LINK.exec(text.trim());
  return match && !text.includes("diff --git") ? `${match[0]}.diff` : null;
}

type Phase =
  | { kind: "idle" }
  | { kind: "link"; diffUrl: string }
  | { kind: "loading"; files: number }
  | { kind: "error" }
  | { kind: "result"; result: SummarizeResult };

export function TryDiff() {
  const [diff, setDiff] = useState("");
  const [title, setTitle] = useState("");
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const diffStore = useDiffStore();

  async function run() {
    const diffUrl = diffLinkFor(diff);
    if (diffUrl) {
      setPhase({ kind: "link", diffUrl });
      return;
    }
    setPhase({ kind: "loading", files: countFiles(diff) });
    try {
      const result = await summarize(diff, title);
      diffStore.set(result.run_id, diff); // tab memory only, for the Review screen
      setPhase({ kind: "result", result });
    } catch {
      setPhase({ kind: "error" });
    }
  }

  const loading = phase.kind === "loading";

  return (
    <div className="page">
      <header>
        <h1>
          Try a diff <span className="tag">Dev only</span>
        </h1>
        <p className="meta">
          Open your PR on GitHub with <code>.diff</code> added to the end of its URL, copy all of
          that text and paste it here. We send the code
          files to the AI for this summary only and don&apos;t store the diff. Nothing is posted to
          GitHub.
        </p>
      </header>

      <section className="form">
        <label>
          PR title <span className="meta">(optional)</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} disabled={loading} />
        </label>
        <label>
          Diff
          <textarea
            className="mono"
            rows={12}
            value={diff}
            onChange={(e) => setDiff(e.target.value)}
            placeholder="diff --git a/src/app.py b/src/app.py ..."
            disabled={loading}
            spellCheck={false}
          />
        </label>
        <button className="primary" onClick={run} disabled={loading || diff.trim() === ""}>
          Summarize
        </button>
      </section>

      <section aria-live="polite">
        {phase.kind === "idle" && <p className="meta">Paste a diff to see the summary.</p>}
        {phase.kind === "link" && (
          <div className="notice">
            <p>That&apos;s a link to the PR, not the diff. Nothing was sent.</p>
            <p>
              Open{" "}
              <a href={phase.diffUrl} target="_blank" rel="noreferrer" className="mono">
                {phase.diffUrl}
              </a>
              , press Ctrl+A then Ctrl+C, and paste that text here instead of the link.
            </p>
          </div>
        )}
        {phase.kind === "loading" && <p>Reading {phase.files} files...</p>}
        {phase.kind === "error" && (
          <div className="notice error">
            <p>Couldn&apos;t reach the server. Nothing was posted.</p>
            <button onClick={run}>Try again</button>
          </div>
        )}
        {phase.kind === "result" && <Result result={phase.result} />}
      </section>
    </div>
  );
}

function Result({ result }: { result: SummarizeResult }) {
  if (result.status !== "done" || !result.comment_markdown) {
    return (
      <div className={`notice ${result.status === "failed" ? "error" : ""}`}>
        <p>{result.message}</p>
        {result.skipped.length > 0 && (
          <p className="meta">
            Skipped:{" "}
            {result.skipped.map((s) => (
              <code key={s.path}>{s.path} </code>
            ))}
          </p>
        )}
      </div>
    );
  }
  return (
    <div className="result">
      <h2>Comment preview</h2>
      <p className="meta">
        {result.message} Read {result.files_kept} of {result.files_total} files. Run{" "}
        <code>#{result.run_id}</code>.
      </p>
      <pre className="mono comment-raw" data-testid="comment">
        {result.comment_markdown}
      </pre>
      <p className="ai-note">Written by AI. It can be wrong.</p>
      <div className="row-actions">
        <CopyButton text={result.comment_markdown} />
        <Link to={`/review/${result.run_id}`}>Open the review with the diff</Link>
      </div>
      {result.summary_id !== null && <VerdictForm summaryId={result.summary_id} />}
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
      }}
    >
      {copied ? "Copied" : "Copy comment"}
    </button>
  );
}

function VerdictForm({ summaryId }: { summaryId: number }) {
  const [accurate, setAccurate] = useState<Verdict["accurate"] | null>(null);
  const [savedTime, setSavedTime] = useState<boolean | null>(null);
  const [note, setNote] = useState("");
  const [state, setState] = useState<"editing" | "saving" | "saved" | "error">("editing");

  if (state === "saved") return <p className="notice">Verdict saved. Thank you.</p>;

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
    <fieldset className="verdict">
      <legend>Reviewer verdict</legend>
      <p>Is this summary accurate?</p>
      <div className="choices" role="radiogroup" aria-label="Accurate">
        {(["yes", "partly", "no"] as const).map((v) => (
          <label key={v}>
            <input
              type="radio"
              name="accurate"
              checked={accurate === v}
              onChange={() => setAccurate(v)}
            />
            {v}
          </label>
        ))}
      </div>
      <p>Would it have saved you time on this PR?</p>
      <div className="choices" role="radiogroup" aria-label="Saved time">
        {[true, false].map((v) => (
          <label key={String(v)}>
            <input
              type="radio"
              name="saved"
              checked={savedTime === v}
              onChange={() => setSavedTime(v)}
            />
            {v ? "yes" : "no"}
          </label>
        ))}
      </div>
      <label>
        What was actually slow about reviewing it?
        <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      {state === "error" && <p className="error-text">Couldn&apos;t save. Your summary is fine.</p>}
      <button onClick={submit} disabled={!accurate || state === "saving"}>
        Save verdict
      </button>
    </fieldset>
  );
}

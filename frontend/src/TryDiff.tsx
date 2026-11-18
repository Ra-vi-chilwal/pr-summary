import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ApiError,
  type SummarizeResult,
  type Verdict,
  countFiles,
  isPrLink,
  saveVerdict,
  summarize,
} from "./api";
import { useDiffStore } from "./diffStore";

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
      // Tab memory only, for the Review screen. For a link, the backend sends back the diff it read.
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
      <header>
        <h1>
          Try a diff <span className="tag">Dev only</span>
        </h1>
        <p className="meta">
          Paste the link to a <b>public</b> GitHub pull request (for example{" "}
          <code>https://github.com/you/repo/pull/1</code>), or paste the diff text itself. We send
          the code files to the AI for this summary only and don&apos;t store the diff. Nothing is
          posted to GitHub.
        </p>
      </header>

      <section className="form">
        <label>
          PR title <span className="meta">(optional)</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} disabled={loading} />
        </label>
        <label>
          PR link or diff
          <textarea
            className="mono"
            rows={8}
            value={diff}
            onChange={(e) => setDiff(e.target.value)}
            placeholder="https://github.com/you/repo/pull/1"
            disabled={loading}
            spellCheck={false}
          />
        </label>
        <button className="primary" onClick={run} disabled={loading || diff.trim() === ""}>
          Summarize
        </button>
      </section>

      <section aria-live="polite">
        {phase.kind === "idle" && <p className="meta">Paste a PR link to see the summary.</p>}
        {phase.kind === "loading" && <p>{phase.text}</p>}
        {phase.kind === "error" && (
          <div className="notice error">
            <p>{phase.message ?? "Couldn't reach the server. Nothing was posted."}</p>
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

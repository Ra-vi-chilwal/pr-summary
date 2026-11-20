import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { isPrLink } from "../api";
import { useSession } from "../session";
import "./landing.css";

/*
 * The public home page. Everything in the product preview is made-up sample data
 * (repo, people, code) and says so under the frame.
 */

const REPO = "sample-team/checkout";

const SAMPLE = {
  pr: 482,
  title: "Retry failed card payments",
  overview:
    "Failed card payments now get retried up to three times, with a short wait between tries. The retry logic lives in a new payments/retry.py, and the webhook handler calls it instead of marking the order failed straight away.",
  check: [
    {
      path: "payments/retry.py",
      why: "If the charge went through but the response timed out, a retry could charge the card again. There's no idempotency key.",
    },
    {
      path: "webhooks/payment_events.py",
      why: "Orders stay “pending” while retries run. Code that waits for “failed” won't see them until all three tries are done.",
    },
    {
      path: "config/settings.py",
      why: "RETRY_LIMIT has no upper bound. A big value could leave a customer waiting for minutes.",
    },
  ],
  files: [
    { path: "payments/retry.py", note: "New. Retries a charge up to RETRY_LIMIT times, waiting a bit longer each time." },
    { path: "webhooks/payment_events.py", note: "Calls the retry helper instead of failing the order on the first error." },
    { path: "config/settings.py", note: "Adds RETRY_LIMIT, default 3." },
    { path: "tests/test_retry.py", note: "Covers a charge that works on the second try, and giving up after three." },
    { path: "migrations/0042_attempts.py", note: "Could not tell what this file does.", unsure: true },
  ],
};

type Tab = "comment" | "dashboard" | "review";
const TABS: { id: Tab; label: string; caption: string }[] = [
  { id: "comment", label: "Comment", caption: "The one comment it leaves on the pull request." },
  { id: "dashboard", label: "Dashboard", caption: "Every PR it has read, and what happened to each." },
  { id: "review", label: "Review", caption: "Open any summary and go through it file by file." },
];

export function Landing() {
  const { loading, me } = useSession();
  if (!loading && me.user) return <Navigate to="/dashboard" replace />;

  return (
    <div className="lp">
      <a className="skip-link" href="#lp-main">
        Skip to content
      </a>
      <header className="lp-nav">
        <div className="lp-nav-inner">
          <Link to="/" className="brand">
            <span className="brand-mark" aria-hidden="true">
              PR
            </span>
            PR Summary
          </Link>
          <a className="lp-nav-link lp-hide-sm" href="#how">
            How it works
          </a>
          <span className="lp-spacer" />
          <Link className="lp-nav-link" to="/login">
            Sign in
          </Link>
          <Link className="btn lp-btn-ink" to="/signup">
            Try for free
          </Link>
        </div>
      </header>

      <main id="lp-main">
        <section className="lp-hero">
          <h1 className="lp-display">Know what a pull request changed before you open the diff.</h1>
          <p className="lp-lead">
            PR Summary leaves one comment on each pull request: what changed, a short note per file,
            and the two or three files to check first. New commits update the same comment.
          </p>
          <Link className="btn btn-lg lp-btn-ink" to="/signup">
            Try for free
          </Link>
          <p className="lp-fine">Reads your code. Never approves, merges or pushes.</p>
          <a className="lp-underline" href="#paste">
            or paste a PR link
          </a>
        </section>

        <Preview />

        <section className="lp-section" id="how" aria-labelledby="how-title">
          <p className="lp-kicker">How it works</p>
          <h2 className="lp-display lp-h2" id="how-title">
            Install it. Open a PR. Read one comment.
          </h2>
          <div className="lp-cards">
            <article className="lp-card">
              <div className="lp-card-art">
                <div className="mini-panel">
                  <p className="mini-label">Repository access</p>
                  <MiniCheck on label="checkout" />
                  <MiniCheck on label="notifications" />
                  <MiniCheck label="search" />
                </div>
              </div>
              <h3 className="lp-card-title">Install it on the repos you pick</h3>
              <p className="lp-card-text">
                GitHub's own screen shows what it can see. Start with one repo; you can add more later.
              </p>
            </article>

            <article className="lp-card">
              <div className="lp-card-art">
                <div className="mini-panel">
                  <p className="mini-pr">
                    <span className="mini-open">Open</span> #{SAMPLE.pr} {SAMPLE.title}
                  </p>
                  <p className="mini-meta mono">
                    6 files changed <span className="add">+184</span> <span className="del">−22</span>
                  </p>
                </div>
              </div>
              <h3 className="lp-card-title">Open a pull request like always</h3>
              <p className="lp-card-text">Nothing new to learn. No commands to type, no labels to add.</p>
            </article>

            <article className="lp-card">
              <div className="lp-card-art">
                <div className="mini-panel">
                  <p className="mini-bot">
                    <span className="mini-avatar" aria-hidden="true" />
                    pr-summary <span className="muted">· edited</span>
                  </p>
                  <p className="mini-commit mono">
                    <span className="strike">a1f3c2d</span> → 9be41d0
                  </p>
                  <p className="mini-meta">Same comment, rewritten for the new commit.</p>
                </div>
              </div>
              <h3 className="lp-card-title">One comment, kept up to date</h3>
              <p className="lp-card-text">
                Push more commits and it rewrites the comment it already left. Your PR doesn't fill up
                with bot replies.
              </p>
            </article>

            <article className="lp-card">
              <div className="lp-card-art">
                <div className="mini-panel">
                  <p className="mini-label">Check these first</p>
                  <p className="mini-risk high mono">payments/retry.py</p>
                  <p className="mini-risk med mono">webhooks/payment_events.py</p>
                  <p className="mini-risk med mono">config/settings.py</p>
                </div>
              </div>
              <h3 className="lp-card-title">Check the risky files first</h3>
              <p className="lp-card-text">
                Each pick comes with one line on why. Start there, then skim the rest.
              </p>
            </article>
          </div>
        </section>

        <section className="lp-narrow" aria-labelledby="marks-title">
          <h2 className="lp-display lp-h3" id="marks-title">
            What the summary tells you
          </h2>
          <p className="lp-sub">Every file lands in one of these.</p>
          <dl className="lp-marks">
            <div>
              <dt>
                <span className="mark mark-high">Check first</span>
              </dt>
              <dd>The file most likely to break something. The reason is right under it.</dd>
            </div>
            <div>
              <dt>
                <span className="mark mark-med">Also check</span>
              </dt>
              <dd>One or two more files worth a careful look, each with its own reason.</dd>
            </div>
            <div>
              <dt>
                <span className="mark mark-unsure">Couldn't tell</span>
              </dt>
              <dd>The AI wasn't sure what the file does, so it says that instead of guessing.</dd>
            </div>
            <div>
              <dt>
                <span className="mark mark-skip">Skipped</span>
              </dt>
              <dd>Lockfiles, generated files and images. They're listed, not read.</dd>
            </div>
          </dl>
        </section>

        <PasteLink />

        <section className="lp-narrow lp-trust" aria-label="What it promises">
          <p>
            <strong>Your diff isn't stored.</strong> It's read, summarized and dropped. Only the summary
            is kept.
          </p>
          <p>
            <strong>Nothing half-done.</strong> If anything fails, nothing is posted on GitHub.
          </p>
          <p>
            <strong>It knows it's a bot.</strong> Every summary ends with &ldquo;Written by AI. It can be
            wrong.&rdquo;
          </p>
        </section>
      </main>

      <footer className="lp-footer">
        <div className="lp-footer-inner">
          <span>PR Summary · Reads your code. Never merges.</span>
          <span className="lp-spacer" />
          <Link to="/try">Try a diff</Link>
          <Link to="/login">Sign in</Link>
          <Link to="/signup">Create an account</Link>
        </div>
      </footer>
    </div>
  );
}

function MiniCheck({ on = false, label }: { on?: boolean; label: string }) {
  return (
    <p className={`mini-check ${on ? "on" : ""}`}>
      <span className="box" aria-hidden="true" />
      {label}
    </p>
  );
}

function Preview() {
  const [tab, setTab] = useState<Tab>("comment");
  const current = TABS.find((t) => t.id === tab)!;

  return (
    <section className="lp-preview" aria-label="Product preview">
      <div className="lp-tabs" role="tablist" aria-label="Preview">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls="preview-panel"
            className={`lp-tab ${tab === t.id ? "on" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <p className="lp-caption">{current.caption}</p>
      <div className="lp-frame" role="tabpanel" id="preview-panel" aria-labelledby={`tab-${tab}`}>
        {tab === "comment" && <CommentShot />}
        {tab === "dashboard" && <DashboardShot />}
        {tab === "review" && <ReviewShot />}
      </div>
      <p className="lp-fine">Sample data: a made-up repo, people and code.</p>
    </section>
  );
}

function CommentShot() {
  return (
    <div className="cs">
      <div className="cs-pr">
        <p className="cs-repo mono">{REPO}</p>
        <p className="cs-title">
          {SAMPLE.title} <span className="muted">#{SAMPLE.pr}</span>
        </p>
      </div>
      <div className="cs-comment">
        <div className="cs-head">
          <span className="mini-avatar" aria-hidden="true" />
          <strong>pr-summary</strong>
          <span className="cs-bot">bot</span>
          <span className="muted">commented · edited after 2 new commits</span>
        </div>
        <div className="cs-body">
          <h3>PR summary</h3>
          <p>{SAMPLE.overview}</p>
          <h4>Check these first</h4>
          <ol className="cs-check">
            {SAMPLE.check.map((c, i) => (
              <li key={c.path} className={i === 0 ? "high" : "med"}>
                <code>{c.path}</code>: {c.why}
              </li>
            ))}
          </ol>
          <h4>What changed, file by file</h4>
          <ul className="cs-files">
            {SAMPLE.files.map((f) => (
              <li key={f.path}>
                <code>{f.path}</code>: <span className={f.unsure ? "muted" : undefined}>{f.note}</span>
              </li>
            ))}
            <li className="muted">
              <code>package-lock.json</code>: skipped, lockfile.
            </li>
          </ul>
          <p className="cs-foot">Written by AI. It can be wrong.</p>
        </div>
      </div>
    </div>
  );
}

const ROWS = [
  { title: SAMPLE.title, where: `checkout #${SAMPLE.pr}`, status: "Posted · updated 2 min ago", kind: "ok" },
  { title: "Move email templates into one folder", where: "notifications #77", status: "Posted", kind: "ok" },
  { title: "Bump dependencies", where: "checkout #480", status: "Skipped: only lockfiles", kind: "skip" },
  { title: "Rewrite the search indexer", where: "search #211", status: "Skipped: 143 files", kind: "skip" },
  { title: "Add a theme switch to settings", where: "web #1290", status: "Failed, nothing posted", kind: "bad" },
];

function DashboardShot() {
  return (
    <div className="ds">
      <aside className="ds-side" aria-hidden="true">
        <p className="ds-brand">
          <span className="brand-mark">PR</span> PR Summary
        </p>
        <p className="ds-nav on">Dashboard</p>
        <p className="ds-nav">Try a diff</p>
        <p className="ds-group">Repositories</p>
        <p className="ds-nav">checkout</p>
        <p className="ds-nav">notifications</p>
        <p className="ds-nav">search</p>
      </aside>
      <div className="ds-main">
        <div className="ds-top">
          <p className="ds-h">Dashboard</p>
          <p className="muted small">This month: 23 of 50 summaries · $0.41 of $10</p>
        </div>
        <ul className="ds-rows">
          {ROWS.map((r) => (
            <li key={r.title} className="ds-row">
              <span className="ds-title">{r.title}</span>
              <span className="ds-where mono">{r.where}</span>
              <span className={`ds-status ${r.kind}`}>
                <span className="dot" aria-hidden="true" />
                {r.status}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function ReviewShot() {
  const marks = ["high", "med", "med", "", "unsure"];
  return (
    <div className="rs">
      <aside className="rs-files">
        <p className="mini-label">6 files · 5 read</p>
        {SAMPLE.files.map((f, i) => (
          <p key={f.path} className={`rs-file mono ${marks[i]} ${i === 0 ? "on" : ""}`}>
            {f.path}
          </p>
        ))}
        <p className="rs-file mono skip">package-lock.json</p>
      </aside>
      <div className="rs-main">
        <p className="rs-path mono">payments/retry.py</p>
        <div className="rs-why">
          <strong>Check this first</strong>
          <span>{SAMPLE.check[0].why}</span>
        </div>
        <p className="rs-note">
          <span className="mini-label">AI note</span>
          {SAMPLE.files[0].note}
        </p>
        <pre className="rs-diff mono" aria-label="Sample diff">
          <span className="hunk">@@ -0,0 +1,9 @@</span>
          {"\n"}
          <span className="add">+def charge_with_retry(order, limit=RETRY_LIMIT):</span>
          {"\n"}
          <span className="add">+    for attempt in range(limit):</span>
          {"\n"}
          <span className="add">+        result = gateway.charge(order.card, order.total)</span>
          {"\n"}
          <span className="add">+        if result.ok:</span>
          {"\n"}
          <span className="add">+            return result</span>
          {"\n"}
          <span className="add">+        sleep(2 ** attempt)</span>
        </pre>
      </div>
    </div>
  );
}

function PasteLink() {
  const [link, setLink] = useState("");
  const navigate = useNavigate();
  const ok = isPrLink(link);
  const touched = link.trim().length > 0;

  return (
    <section className="lp-narrow lp-paste" id="paste" aria-labelledby="paste-title">
      <h2 className="lp-h4" id="paste-title">
        No GitHub App yet? Paste a PR link
      </h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (ok) navigate(`/try?pr=${encodeURIComponent(link.trim())}`);
        }}
      >
        <label className="field-label" htmlFor="lp-link">
          Pull request link
        </label>
        <input
          id="lp-link"
          className="input"
          type="url"
          inputMode="url"
          placeholder="https://github.com/owner/repo/pull/123"
          value={link}
          onChange={(e) => setLink(e.target.value)}
          aria-describedby="lp-link-hint"
        />
        <p className="lp-hint" id="lp-link-hint">
          {touched && !ok
            ? "That doesn't look like a pull request link. It should end in /pull/ and a number."
            : "Public repos work right away. Private ones need the app installed."}
        </p>
        <button className="btn lp-btn-ink" type="submit" disabled={!ok}>
          Summarize this PR
        </button>
      </form>
    </section>
  );
}

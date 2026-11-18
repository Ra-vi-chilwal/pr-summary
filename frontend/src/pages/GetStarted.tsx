import { Link } from "react-router-dom";
import { ProductShot } from "../components/ProductShot";
import { useSession } from "../session";

const STEPS = [
  {
    title: "Install on one repository",
    text: "GitHub's own screen shows the exact permissions. You choose the repositories; nothing else is touched.",
  },
  {
    title: "Open a pull request",
    text: "We read the changed files, skip lockfiles, generated files and images, and send the code to the AI for this summary only.",
  },
  {
    title: "Read one comment",
    text: "What changed, a note per file, and the two or three files worth checking first. New commits edit the same comment.",
  },
];

const NEVER = [
  ["Approve, merge or close", "It only reads the diff and writes its own comment."],
  ["Post a second comment", "New commits update the existing summary in place."],
  ["Keep your code", "The diff is read, summarized and dropped. Only the summary is saved."],
  ["Pretend to be human", "Every summary ends with “Written by AI. It can be wrong.”"],
];

export function GetStarted() {
  const { me } = useSession();
  const connected = me.installations.length > 0;

  return (
    <div className="page">
      <section className="landing">
        <div className="landing-copy">
          <p className="eyebrow">For developers who review a lot of PRs</p>
          <h1>Know what a pull request does before you open the diff.</h1>
          <p className="lead">
            PR Summary leaves one comment on each pull request: what changed, a short note per
            file, and the files a reviewer should check first.
          </p>
          <div className="actions">
            {connected ? (
              <Link className="btn btn-primary btn-lg" to="/dashboard">
                Open your dashboard
              </Link>
            ) : me.user ? (
              <a
                className="btn btn-primary btn-lg"
                href="/api/github/install"
                aria-disabled={!me.github_app_configured}
                onClick={(e) => !me.github_app_configured && e.preventDefault()}
              >
                Connect GitHub
              </a>
            ) : (
              <Link className="btn btn-primary btn-lg" to="/signup">
                Create an account
              </Link>
            )}
            <Link className="link-arrow" to="/try">
              Try a public PR first →
            </Link>
          </div>
          {me.user && !connected && !me.github_app_configured && (
            <p className="small muted">
              The GitHub App isn&apos;t configured on this server yet. See “Create the GitHub App” in
              the README.
            </p>
          )}
        </div>
        <ProductShot />
      </section>

      <section className="section" aria-labelledby="how">
        <div className="section-head">
          <h2 id="how">How it works</h2>
        </div>
        <ol className="steps">
          {STEPS.map((s, i) => (
            <li key={s.title}>
              <span className="eyebrow">Step {i + 1}</span>
              <h3>{s.title}</h3>
              <p className="muted">{s.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="section" aria-labelledby="never">
        <div className="section-head">
          <h2 id="never">What it will never do</h2>
        </div>
        <ul className="never">
          {NEVER.map(([title, text]) => (
            <li key={title}>
              <span className="status-dot bad" style={{ marginTop: "var(--space-2)" }} />
              <span>
                <strong>{title}.</strong> <span className="muted">{text}</span>
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

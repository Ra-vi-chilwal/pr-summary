import { Link } from "react-router-dom";

const STEPS = [
  {
    title: "Install on one repository",
    text: "GitHub shows exactly which permissions we ask for. You pick one repo, not your whole organization.",
  },
  {
    title: "Open a pull request",
    text: "We read the changed files and skip lockfiles, generated files and images. The code is sent to the AI for the summary only; we don't keep it.",
  },
  {
    title: "Read the summary on GitHub",
    text: "One comment on the PR: what changed, a note per file, and the files to check first. It is edited on new commits, never repeated.",
  },
];

export function GetStarted() {
  return (
    <div className="page">
      <div className="hero">
        <div className="hero-main">
          <h1>Know what a pull request does before you open the diff.</h1>
          <p>
            We read every pull request and post a short summary on it, with the files to check
            first. For developers who review a lot of PRs.
          </p>
          <button className="primary" disabled aria-describedby="connect-note">
            Connect a GitHub repo
          </button>
          <p id="connect-note" className="meta">
            Not available yet: this needs the GitHub App to be set up. Until then,{" "}
            <Link to="/try">try it on a diff</Link>.
          </p>
        </div>
        <div className="hero-steps">
          <h2>Get started in three steps</h2>
          <ol className="steps">
            {STEPS.map((s, i) => (
              <li key={s.title}>
                <span className="step-num">{i + 1}</span>
                <span className="step-title">{s.title}</span>
                <span className="step-text">{s.text}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  );
}

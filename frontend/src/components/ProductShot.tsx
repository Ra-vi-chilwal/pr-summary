/**
 * A product shot made from a real summary: run #10 of this app on
 * Ra-vi-chilwal/trustRush-fastAPI PR #1 (gemini-3.8-flash), shortened for space.
 */
const SHOT = {
  repo: "trustRush-fastAPI",
  pr: 1,
  title: "chnage in the branch",
  overview:
    "Integrates RabbitMQ messaging into the FastAPI backend: connection lifecycle on startup, queue and exchange topology, and a signup route that publishes a registration event.",
  check: [
    {
      path: "backend/messaging/publisher.py",
      why: "The file is empty, but auth/routes.py imports publish_event from it, which will fail at runtime.",
    },
    {
      path: "backend/config.py",
      why: "RABBITMQ_URL has no default, so the app won't start if it's missing.",
    },
    {
      path: "backend/auth/routes.py",
      why: "Publishing inside signup can fail or delay registration without error handling.",
    },
  ],
};

export function ProductShot({ compact = false }: { compact?: boolean }) {
  const items = compact ? SHOT.check.slice(0, 2) : SHOT.check;
  return (
    <figure style={{ margin: 0 }}>
      <div className="shot">
        <div className="shot-bar">
          <span className="mono">
            {SHOT.repo} #{SHOT.pr}
          </span>
          <span className="badge">1 comment · edited on new commits</span>
        </div>
        <div className="shot-body">
          <div>
            <h3>What changed</h3>
            <p className="muted">{SHOT.overview}</p>
          </div>
          <div>
            <h3 style={{ marginBottom: "var(--space-3)" }}>Check these first</h3>
            <ol className="check-list">
              {items.map((c, i) => (
                <li key={c.path} className={`check-item ${i === 0 ? "first" : ""}`}>
                  <span className="check-num">{i + 1}</span>
                  <span className="check-path">{c.path}</span>
                  <span className="check-why">{c.why}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
        <div className="shot-foot">13 of 14 files read · 1 lockfile skipped · Written by AI. It can be wrong.</div>
      </div>
      <figcaption className="shot-caption">A real summary of an open pull request, shortened.</figcaption>
    </figure>
  );
}

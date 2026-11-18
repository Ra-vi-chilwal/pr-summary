# PROGRESS.md

## 2026-11-18: App UI (shell, Get started, Dashboard, Review)

### Done
- Sidebar shell on every screen (React Router). Phone width: the sidebar becomes a top bar.
- **Get started**: DESIGN.md §5 headline, plus "Get started in three steps". The "Connect a GitHub repo"
  button is disabled with an honest note until the GitHub App exists.
- **Dashboard**: real runs from the DB, newest first; "N runs this month · AI spend $x of $10";
  failed runs say "Failed, nothing posted"; loading, empty and error-with-retry states.
- **Review**: Overview (what changed, check these first, all files, AI warning) plus a per-file view
  with the check-first reason, the AI note and a GitHub-style side-by-side diff. The diff exists only in
  the browser tab's memory (from Try a diff); otherwise the screen says "The diff isn't stored".
- Backend: `GET /api/dev/runs` and `GET /api/dev/runs/{id}` (dev-only). They never return a diff.
- New package: `react-router-dom` 6.28.0.

### Checks run
- Backend: 42 passed, ruff clean. Frontend: 18 passed (diff parser, Dashboard, Review, Get started,
  Try a diff), lint clean, build OK.
- Screenshots at desktop and phone width. The Review "done" screenshots use API replies faked inside
  the screenshot browser only, because no real summary exists yet (no AI key).

### What broke
- Another project (`D:\Whiteboard Hour\frontend`) runs Vite on localhost:5173, so browsers opened it
  instead of this app. **This app now runs on http://localhost:5180.**

### Still waiting on you
- Gemini decision (privacy trade-off) and a new key in `.env` (the pasted key should be revoked).
- The GitHub App, for "Connect a GitHub repo", sign-in and the Connected screen.
- Layers (grouping files) in Review need a prompt change: a later step.

## 2026-11-17: Milestone 1 code done, real AI run still pending

### Decisions (from you)
- Stack: React + TS (Vite) frontend, FastAPI backend, Postgres (Neon in prod, local container in dev). No Convex.
- Model: Claude Opus 5.5 (`claude-opus-5-5`), effort `high`, structured JSON output, server-side refusal fallback on.
- A dev-only "Try a diff" screen (not in DESIGN.md; only on when `ENABLE_DEV_TOOLS=true`).
- API key added later. Without it, runs end "Failed, nothing posted."

### Done
- `backend/`: parse diff → skip lockfiles/generated/images → skip >100 files or a huge diff →
  check $10 monthly spend → one Claude call (+1 retry on retryable errors) → check the answer
  against the real file list → GitHub markdown comment ending "Written by AI. It can be wrong."
- Tables `repos`, `runs`, `summaries` (+ reviewer verdict), `usage` (tokens and cost). The diff is never stored.
- `frontend/`: Try a diff page with empty, loading ("Reading N files..."), skipped, failed,
  error-with-retry and done states, copy button and verdict form.
- `docker-compose.yml`: db + api + web. `.env.example`, `.gitignore` (blocks `.env`, keys).

### Checks run (real results)
- Backend: `uv run pytest`: 41 passed. `ruff check` and `ruff format --check` are clean.
- Frontend: `npm test`: 7 passed. `npm run lint` is clean. `npm run build` OK.
- docker compose: all 3 containers up; tables created in Postgres; a lockfile-only diff was
  skipped with no AI call; a code diff without a key ended "Failed, nothing posted." and both runs were logged.
- Screenshots (desktop 1280px, phone 390px): empty, skipped and failed states.
  The done state needs a real AI run, so it has not been captured yet.

| BUILD.md test | Status |
|---|---|
| 4 Only lockfiles | Passed (unit test + real compose run) |
| 5 Too big (100+ files) | Passed (unit test) |
| 7 AI down: 1 retry, nothing posted | Passed (unit test with a fake AI) |
| 8 Unclear code says it isn't sure | Formatting passed (unit test); the real AI behaviour is untested |
| 1, 2, 3, 6 | Milestones 2–4 |

### What broke
- `docker compose up --build` fails on this Windows machine (Compose v5 "bake" asks for
  `--allow=fs.read=...\Dockerfile`). Workaround:
  `docker build -t pr-reviewer-api ./backend; docker build -t pr-reviewer-web ./frontend; docker compose up -d --no-build`
- Node on this machine is 18.15 (end of life). Frontend tool versions are pinned to work with it; the docker image uses Node 20.

### Open
- BUILD.md still describes Convex. It should be updated to FastAPI + Neon (your doc, your call).
- The folder is not a git repo yet, and `Ra-vi-chilwal/pr-summary` isn't created. Nothing has been committed or pushed.
- The "50 reviews per repo per month" cap starts in Milestone 2, when runs have a repo.
- Tables are created at startup. Add Alembic migrations before Neon/production.

### Next
See PLAN.md: the real run on one of your PRs, plus a reviewer verdict.

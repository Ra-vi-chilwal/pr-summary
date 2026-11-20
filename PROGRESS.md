# PROGRESS.md

## 2026-11-20: Live on Vercel + Neon, landing page

### Done
1. **Vercel deploy fixed**: module-level `app`, Neon `postgresql://` URLs accepted, migrations run on
   start (advisory lock), webhooks finish before answering on Vercel.
2. **`/api/health/db`**: says if the database is reachable, with a safe reason label (never the URL).
   It found the cause of the signup 500: Vercel's `DATABASE_URL` pointed at localhost. Fixed by you
   (Neon link in Vercel).
3. **Direct links**: `/login`, `/signup`, `/dashboard` etc. no longer 404 on Vercel. Review links are
   now `/review?run=ID`; `/review/ID` still works inside the app.
4. **`JWT_SECRET_KEY`** is accepted as the secret key name too.
5. **Landing page at `/`**: hero, product preview with Comment / Dashboard / Review tabs (made-up
   sample data, labelled), how it works (4 cards), what the summary tells you, paste a PR link
   (opens Try a diff filled in), trust notes, footer. Instrument Serif (self-hosted) for headlines.
   Signed-in visitors go to the Dashboard. The old Get started page moved to `/get-started`.

### Checks run (real results)
- Live site: health/db ok (revision 0002); signup, me, logout, login all worked; one real summary
  via Try a diff (took ~2m45s).
- Backend: **161 passed**, ruff clean. Frontend: **62 passed**, lint and types clean.
- Landing screenshots at 1440px and 390px: no sideways scroll.

### Left in the live DB
- Test user `deploy-check-...@example.com` (user #1) and run #1. Delete on request.

### Broke / watch
- Summaries can be slow on Vercel (~2-3 min): raise Function Max Duration if they time out.
- Hosting is Vercel, but AGENTS.md still says Render: please update AGENTS.md.

## 2026-11-18: Redesign, accounts, GitHub App, logging

### Done (5 commits)
1. **Design system**: `frontend/src/design/tokens.css` (colours, type scale, spacing, radii, motion),
   with WCAG AA contrast checked by tests. Self-hosted Geist and JetBrains Mono fonts.
2. **Redesign**: sidebar shell (connection status, account, mobile drawer); Get started; Dashboard
   (usage, repos with a Private badge, open PRs, recent summaries); Try a diff; Summary page with a
   sticky file list, coverage meter explaining skipped files, numbered check-first items with a risk
   rule, skeleton loaders and a copy toast; error boundary; frontend logger.
3. **Logging foundation**: structlog JSON with `LOG_LEVEL`, request IDs, a redaction filter, an
   `audit_log` table, and Alembic migrations (0001 adopted the existing local database: 11 old runs kept).
4. **Accounts**: signup and login (argon2id) with a strength hint, httpOnly SameSite=Lax session
   cookies, CSRF, per-IP and per-email rate limits, field-level messages, GitHub sign-in, and
   protected Dashboard and Summary routes. Try a diff stays public. Forgot password is a placeholder.
5. **GitHub App**: install flow, links an installation only after GitHub confirms it's the user's,
   cached installation tokens, repos and PRs, private PR links on Try a diff, webhook (signature,
   installation events, one comment per PR edited on new commits, no duplicate AI calls, nothing
   posted on failure, 50 per repo per month), clear errors.
6. README: how to run locally and how to create the GitHub App.

### Checks run (real results)
- Backend: **155 passed**, ruff clean. Frontend: **57 passed**, lint, types and build clean.
- docker: migrations applied to the existing Postgres. Real signup → session → protected runs through
  localhost:5180. A POST without the CSRF token got 403. The audit log recorded the signup.
- Logs scanned for the test password, session cookie, API keys, tokens, PEM, diff text and DB
  password: 0 hits each.
- Screenshots at desktop and phone width for signup, login errors, Get started, Dashboard (real),
  phone menu, and the Try result, Summary, file diff and copy toast (sample data faked in the
  screenshot browser only).

### What broke
- **Gemini returned 503 (overloaded) on 3 real runs today** (runs 12 and 14; the same PR worked
  yesterday). The app did what it should: 1 retry, "Failed, nothing posted.", reason in the logs.
- The screenshots showed a long email spilling out of the sidebar footer. Fixed (ellipsis).
- One test run took 42 minutes once; it couldn't be reproduced (the suite takes about 17 s).

### Not done / needs you
- **The GitHub App isn't created yet**, so "Connect GitHub", GitHub sign-in and webhooks are built and
  tested against a fake GitHub only. Follow README → "Create the GitHub App".
- Webhooks to localhost need smee.io or ngrok (outside services; agree first).
- `SECRET_KEY` isn't set in `backend/.env`, so sign-in state resets on restart. Add it.
- The repo `Ra-vi-chilwal/pr-summary` still can't be reached, so nothing has been pushed.
- PRODUCT.md (login decision) and DESIGN.md (fonts, colours) disagree with the new direction and
  need updating by you.
- Dark mode: not added (light mode is primary, as asked).

## 2026-11-18: Step 1, Gemini option + git

### Decisions (from you)
- Code goes to a new repo `Ra-vi-chilwal/pr-summary` (you create it empty). The prototype repo is untouched.
- You rotate the exposed Gemini key and put the new one in `backend/.env` as `GEMINI_API_KEY`.
- Locally, the app uses its own Postgres container (docker compose), not your `localhost:5433` DB.
- You are the reviewer for the Milestone 1 accuracy check.

### Done
- `GeminiSummarizer` (google-genai 3.5.0, `gemini-3.8-flash`, JSON-schema output). `AI_PROVIDER=gemini|claude`
  picks the AI; Gemini is the default. Cost is tracked at Gemini's paid price ($0.75 / $3.75 per 1M tokens), so the $10 cap stays meaningful.
- docker compose reads `backend/.env`; `DATABASE_URL` is always overridden to the app's own DB.
- `backend/.env.example` documents the settings. Local git repo with the first commit; no secrets
  committed (checked: `.env` ignored, no key-like strings in staged files).

### Checks run
- Backend: 54 passed (12 new Gemini tests with a fake client), ruff clean; imports OK without dev packages.
- docker: API healthy; reports `provider: gemini`, `gemini key set: False` (waiting for your key).

### What broke
- The first docker run crashed: `httpx` is only a test package; both AI SDKs use `httpx2`. Fixed and re-checked.

### Waiting on you
- Create the empty repo `Ra-vi-chilwal/pr-summary` (no README); then I push.
- New key in `backend/.env` as `GEMINI_API_KEY=` (rename the old `API_KEY` line and revoke that key).

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

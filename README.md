# PR Summary

PR Summary reads a GitHub pull request and leaves **one** comment on it: what changed, a short note per
file, and the two or three files a reviewer should check first. New commits edit the same comment.
Every summary ends with “Written by AI. It can be wrong.”

| Part | Tech |
|---|---|
| Frontend | React 18 + TypeScript + Vite, React Router, plain CSS on design tokens (`frontend/src/design/tokens.css`), Geist + JetBrains Mono (self-hosted) |
| Backend | FastAPI (Python 3.12, uv), SQLAlchemy 2, Alembic, structlog |
| Database | Postgres (docker locally, Neon in production) |
| AI | Gemini (`gemini-3.8-flash`, default) or Claude (`claude-opus-5-5`), set by `AI_PROVIDER` |
| GitHub | A GitHub App: webhooks, PR diffs, one comment per PR; GitHub sign-in |

---

## Run it locally

You need **Docker Desktop**. Everything else runs in containers.

```powershell
cd d:\PR-reviewer
copy backend\.env.example backend\.env      # then fill in at least GEMINI_API_KEY and SECRET_KEY
docker build -t pr-reviewer-api ./backend
docker build -t pr-reviewer-web ./frontend
docker compose up -d --no-build
```

Open **http://localhost:5180**. Port 5173 is used by another project on this machine.

- The API applies database migrations every time it starts (`alembic upgrade head`).
- `docker compose up --build` fails on this Windows machine (a Compose "bake" bug), so build the two
  images first, as above.
- Without the GitHub App settings, everything except "Connect GitHub" and GitHub sign-in still works:
  email sign-up, Try a diff with public PR links, the dashboard and summaries.

| Task | Command |
|---|---|
| Stop | `docker compose down` |
| API logs (JSON) | `docker compose logs -f api` |
| Backend tests and lint | `cd backend; uv run pytest; uv run ruff check .` |
| Frontend tests and lint | `cd frontend; npm test; npm run lint; npx tsc --noEmit` |
| New migration | `cd backend; uv run alembic revision -m "what changed"` |

### Settings

All settings live in `backend/.env`, which git ignores. `backend/.env.example` lists every setting with
a comment. Secrets (the AI key, the GitHub App private key and secrets, the DB URL) exist only in backend
env vars, never in the frontend, git or logs.

---

## Create the GitHub App

You need the GitHub App for "Connect GitHub", private repositories, GitHub sign-in and automatic
comments.

### 1. Get a public URL for webhooks (local dev only)

GitHub can't reach `localhost`, so a tunnel has to forward its webhooks to your machine. Two free
options are **smee.io** and **ngrok**. These are outside services, so agree on one before using it.

- **smee.io:** open https://smee.io, click "Start a new channel" and copy the URL. Then run:
  ```powershell
  npx smee-client --url https://smee.io/<your-channel> --target http://localhost:5180/api/github/webhook
  ```
- **ngrok:** `ngrok http 5180`, then use `https://<id>.ngrok-free.app/api/github/webhook`.

The OAuth callback works without a tunnel, because GitHub only redirects your own browser to it.

### 2. Register the app

Go to GitHub → **Settings → Developer settings → GitHub Apps → New GitHub App**.

| Field | Value |
|---|---|
| GitHub App name | e.g. `pr-summary-ravi`. The URL slug of this name is your `GITHUB_APP_SLUG`. |
| Homepage URL | `http://localhost:5180` |
| Callback URL | `http://localhost:5180/api/auth/github/callback` |
| Request user authorization (OAuth) during installation | **On.** We use it to check that the installation is really yours. |
| Setup URL | leave empty (the callback handles installs) |
| Webhook → Active | On |
| Webhook URL | your smee/ngrok URL from step 1 |
| Webhook secret | a long random string; put the same value in `GITHUB_WEBHOOK_SECRET` |

**Repository permissions**

| Permission | Access | Why |
|---|---|---|
| Pull requests | Read and write | read PRs, post and edit our one comment |
| Contents | Read-only | read the diff |
| Metadata | Read-only | required by GitHub |

**Account permissions:** Email addresses → Read-only. This is optional; it lets GitHub sign-in match a
verified email.

**Subscribe to events:** Pull request, Installation (Installation repositories is included).

**Where can this app be installed:** "Only on this account" while testing.

### 3. Copy the values into `backend/.env`

| `.env` key | Where to find it |
|---|---|
| `GITHUB_APP_ID` | App settings page → "App ID" |
| `GITHUB_APP_SLUG` | the last part of `https://github.com/apps/<slug>` |
| `GITHUB_CLIENT_ID` | App settings → "Client ID" |
| `GITHUB_CLIENT_SECRET` | App settings → "Generate a new client secret" |
| `GITHUB_APP_PRIVATE_KEY` | "Generate a private key" downloads a `.pem`. Put it on one line with `\n` escapes (the command is in `.env.example`). Delete the downloaded file afterwards. |
| `GITHUB_WEBHOOK_SECRET` | the secret you typed in step 2 |

Restart the API with `docker compose up -d --force-recreate api`. "Connect GitHub" then works: it sends
you to GitHub's install screen, you pick repositories, and you come back to the dashboard with them
listed (private ones carry a "Private" badge).

---

## How it behaves

- **Try a diff** is public. It takes a PR link or pasted diff text. Private PR links work once your
  installation covers that repo. Signed-out use is rate-limited per IP.
- **Webhook** (`POST /api/github/webhook`): the signature is checked first; any request with a bad
  signature gets a 401. Then:
  - `installation` created/deleted/suspended and `installation_repositories` keep the connection up
    to date.
  - `pull_request` opened/synchronize/reopened summarizes the PR in the background and **creates or
    edits the one comment**.
  - The same commit is never summarized twice.
  - PRs with more than 100 files, or only lockfiles, are skipped.
  - Each repository gets at most 50 summaries a month, and total AI spend stops at $10 a month.
  - If anything fails, nothing is posted, and the dashboard says "Failed, nothing posted".
- **Errors** are spelled out for users: app uninstalled, repository access removed, rate limited, PR
  too large.

## Security

- Passwords are hashed with argon2id.
- Sessions use a random token in an httpOnly, Secure, SameSite=Lax cookie. Only the token's SHA-256 is
  stored in the database.
- Every state-changing `/api` call needs a CSRF token (double-submit cookie). The webhook is the one
  exception; it uses its signature instead.
- Login and signup are rate-limited per IP, and repeated failed logins are blocked per email.
- GitHub sign-in checks the OAuth `state`. An installation is linked to an account only after GitHub
  confirms, with that user's own token, that they can see it.
- Installation tokens are cached in memory and never sent to the browser.
- Anonymous Try-a-diff runs can be claimed only by the browser that created them (a signed cookie).

## Logging

- **Format:** JSON lines on stdout. `LOG_LEVEL` sets the level.
- **Request IDs:** every request gets an `X-Request-ID` (yours is accepted if it's well-formed). The
  same ID appears on every log line for that request and is returned in the response.
- **What's logged:**
  - every request (method, path, status, duration, user id)
  - auth events
  - GitHub calls (endpoint, status, rate-limit remaining)
  - webhooks (received and verified)
  - AI calls (model, tokens, latency, files read vs skipped)
  - errors, with stack traces but no local variables
- **Redaction:** passwords, tokens, cookies, keys and diff contents are always redacted, by key name
  and by value pattern (`app/logging_setup.py`, tested in `tests/test_redaction.py`).
- **Audit log:** the `audit_log` table records signup, login, failed login (email masked), logout,
  GitHub connect and disconnect, repository changes, and summaries posted or failed.
- **Frontend:** a small logger stays quiet in production, and a global error boundary shows a friendly
  page instead of a blank screen.

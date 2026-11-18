# PLAN.md

What we build next. One small feature at a time; wait for "ok" before code.

## Next: connect the real GitHub App (needs you)
1. Add `SECRET_KEY` to `backend/.env` (command in `backend/.env.example`).
2. Create the GitHub App: README → "Create the GitHub App". Put its 6 values in `backend/.env`.
3. `docker compose up -d --force-recreate api`.
4. Sign in at http://localhost:5180, click "Connect GitHub", pick trustRush-fastAPI.
5. Dashboard → the repo → PR #1 → Summarize. (Needs Gemini to be up again.)
6. For automatic comments: pick smee.io or ngrok (outside service: your call), set the webhook URL,
   push a commit to the PR, and check that one comment appears and is edited on the next push.

## Still open from Milestone 1
- A real reviewer verdict on a real summary (the riskiest assumption in PRODUCT.md).

## After that
- Create the empty repo `Ra-vi-chilwal/pr-summary`, then push.
- Go live on Render + Neon (only after you say "deploy").

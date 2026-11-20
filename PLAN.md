# PLAN.md

What we build next. One small feature at a time; wait for "ok" before code.

## Next: connect the real GitHub App (needs you)
Production: Callback `https://pr-summary-six.vercel.app/api/auth/github/callback`, webhook
`https://pr-summary-six.vercel.app/api/github/webhook`, then add the 6 `GITHUB_*` vars in Vercel and redeploy.

1. Secret key: `SECRET_KEY` or `JWT_SECRET_KEY` in `backend/.env`.
2. Create the GitHub App: README → "Create the GitHub App". Put its 6 values in `backend/.env`.
3. `docker compose up -d --force-recreate api`.
4. Sign in at http://localhost:5180, click "Connect GitHub", pick trustRush-fastAPI.
5. Dashboard → the repo → PR #1 → Summarize. (Needs Gemini to be up again.)
6. For automatic comments: pick smee.io or ngrok (outside service: your call), set the webhook URL,
   push a commit to the PR, and check that one comment appears and is edited on the next push.

## Still open from Milestone 1
- A real reviewer verdict on a real summary (the riskiest assumption in PRODUCT.md).

## After that
- Update AGENTS.md: hosting is Vercel (not Render).
- Real Privacy / Terms pages before sharing the site widely.

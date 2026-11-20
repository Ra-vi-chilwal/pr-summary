# PLAN.md

What we build next. One small feature at a time; wait for "ok" before code.

## Next: ship "Link an existing install" (built, waiting for "deploy")
1. You say "deploy": push to `main`, Vercel builds Production.
2. On https://pr-summary-six.vercel.app (signed in): Dashboard → "Already installed the app on
   GitHub? Link it" → approve on GitHub → back on the Dashboard with your repos listed.
3. Open a repo → its open PRs → Summarize. Then open or update a PR to check the automatic comment.

Vercel settings that must stay as they are now: `APP_BASE_URL=https://pr-summary-six.vercel.app`,
`GITHUB_APP_SLUG=pr-summary-ravi` (just the name, not a URL).

## Still open from Milestone 1
- A real reviewer verdict on a real summary (the riskiest assumption in PRODUCT.md).

## After that
- Update AGENTS.md: hosting is Vercel (not Render).
- Real Privacy / Terms pages before sharing the site widely.

# PLAN.md

What we build next. One small feature at a time; wait for "ok" before code.

## Now: finish Milestone 1 (needs you)
Goal: one real PR diff → a summary a reviewer says is accurate and tells them what to check first.
This tests the riskiest guess in PRODUCT.md.

1. Put your new Gemini key in `backend/.env` as `GEMINI_API_KEY=` (see `backend/.env.example`). Never commit it, never paste it in chat.
2. Restart the API: `docker compose up -d --force-recreate api`.
3. Pick one real PR from **your own** repo (~14 files). Open its URL with `.diff` at the end
   (e.g. `https://github.com/Ra-vi-chilwal/<repo>/pull/1.diff`) and copy all of it.
4. Open http://localhost:5180 (moved from 5173, which another project uses), paste the diff, press
   Summarize. Gemini free tier: $0 (counted as about $0.01–0.05 against the $10 cap).
5. You judge it as the reviewer (note: the PR's own author is a weaker test than a second person). Save the verdict in the form.
6. Fill in "What happened" in PRODUCT.md. Decide: keep going / change the problem / change the product.

Gate to Milestone 2: the verdict is "yes" or "partly" and the reviewer says it would have saved time.

## Next: Milestone 2 (plan only, not approved)
Receive the "PR opened" webhook from a GitHub App on one test repo, verify its signature,
fetch the changed files. Still post nothing. Needs: a GitHub App created by you, its secret
and private key in backend env vars.

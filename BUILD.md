Repository and exact commit

Repo: Ra-vi-chilwal/pr-summary (not created yet) Commit: none yet Prototype only: https://github.com/Ra-vi-chilwal/pr-summary-prototype

Smallest milestone and PLAN.md

Milestone: open a PR on a test repo → one AI summary comment shows up on it. PLAN.md:

Create the repo with React + TypeScript + Claude. Runs locally.
Create a GitHub App on my test repo. Save keys in Claude env vars.
Convex HTTP action gets the "PR opened" webhook and checks the secret.
Read the PR diff. Skip lockfiles and generated files.
Send the diff to the AI. Get back summary + "check these first".
Post one comment on the PR. On a new commit, edit the same comment.
Save the run in the database (PR, commit, status).

What I built and how to reproduce it

Not built yet.

Test 

1. Normal PR
   Input: PR with 3-5 code files
   Expected: one comment with summary and files to check
2. New commit
   Input: push to the same PR
   Expected: same comment edited, no new comment
3. Same commit twice
   Input: webhook sent again
   Expected: skipped, no second AI call
4. Only lockfiles
   Input: PR changes only package-lock.json
   Expected: "Nothing to summarize", no AI call
5. Too big
   Input: PR with 100+ files
   Expected: skipped with a message
6. Wrong secret
   Input: fake webhook
   Expected: rejected, nothing posted
7. AI down
   Input: AI call fails
   Expected: 1 retry, then nothing posted, run marked failed
8. Unclear code
   Input: odd or tiny change
   Expected: summary says it is not sure
Each row gets: actual result, commit tested, and a link or screenshot. Only real results count as passed.

Deployment approval and live link, if any
https://ra-vi-chilwal.github.io/pr-summary-prototype/#/review/142

this is the prototype link 
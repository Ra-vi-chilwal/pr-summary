EVALS.md
Cases

For each case: input, expected result, actual result, exact version and proof. Nothing is built yet, so every actual result is "not run yet". Only a real checked result counts as passed.

Normal PR Input: PR with 3-5 code files Expected: one comment with summary and files to check Actual: not run yet · Version: - · Proof: -
New commit Input: push to the same PR Expected: same comment edited, no new comment Actual: not run yet · Version: - · Proof: -
Same commit twice Input: same webhook sent again Expected: skipped, no second AI call Actual: not run yet · Version: - · Proof: -
Only lockfiles Input: PR changes only package-lock.json Expected: "Nothing to summarize", no AI call Actual: not run yet · Version: - · Proof: -
Too big Input: PR with 100+ files Expected: skipped with a message, no AI call Actual: not run yet · Version: - · Proof: -
Empty, loading, error and recovery
Connected, no open PRs Expected: "No open PRs yet."
Dashboard, no runs Expected: "No PRs reviewed yet."
Review while AI is working Expected: "Reading 14 files..." and no blank screen
Dashboard cannot load Expected: "Couldn't load. Your PRs are fine." + Try again
Try again after error Expected: screen loads normally, no duplicate run
Phone width (375 px) Expected: all screens readable, no side scroll, buttons easy to tap For each: Actual: not run yet · Version: - · Proof: screenshot
Access and privacy checks
Wrong webhook secret Input: fake webhook Expected: rejected, nothing posted
Repo not connected to the app Input: PR on another repo Expected: ignored, no AI call
Not signed in Input: open Dashboard without login Expected: sent to sign in, no data shown
Keys not leaked Input: search frontend build, repo and logs for keys Expected: no GitHub key, webhook secret or AI key found
Code not stored Input: check database after a run Expected: summary saved, diff not saved For each: Actual: not run yet · Version: - · Proof: -
AI uncertainty and limits
Unclear code Input: odd or tiny change Expected: summary says it is not sure, does not guess
AI note on every summary Expected: ends with "Written by AI. It can be wrong."
Length cap Expected: summary is 300 words or less
Call cap Expected: max 1 AI call per push, 1 retry
Monthly cap Input: reach 50 reviews in a repo Expected: no more AI calls, dashboard shows limit reached
AI never acts on the PR Expected: no approve, merge, close or push, only its own comment For each: Actual: not run yet · Version: - · Proof: -
Failures and the next correction
AI down Input: AI call fails Expected: 1 retry, then nothing posted, run shows "Failed, nothing posted"
GitHub API down Input: posting the comment fails Expected: run marked failed, no half comment Failures found so far: none, nothing run yet. Next correction: write here what failed, why, and what I will change.
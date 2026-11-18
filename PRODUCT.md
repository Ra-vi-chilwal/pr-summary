# PRODUCT.md

## Job to Be Done
When A developer with 2-5 years of experience, working in a small team, who has just finished a change and opened a pull request on GitHub. and need to review the chnages like now days the AI will chnage alot of files  (They finish coding and open a PR. Now they need someone to review it. The reviewer doesn’t know what changed or which parts are risky, so the PR waits.), I want to They want the reviewer to understand the change quickly and check the risky parts first, so the PR gets reviewed and merged without long waiting or back-and-forth.

like no need to check everything in the manually the complex part only need to review by the senior dev and the UI and small bugs  the proper comments in this , so I can None yet. (Add one only if you have really seen it, e.g. “I saw PRs with one-line descriptions in my own work.”)
what i have seen in my last 5.4 yr of exp the PR description generally empty no one take serially at that time and then in the production the debugging take a lot of time .

## Roles
adoptionApprover: The team lead or engineering manager. (Assumption, I haven’t confirmed this.)
payer: team author or company 
primaryRole: The PR author
problemHolder: the reviewer like the senoir person how take the technical responsibility of the project 
user: the dev team and the comany beccuase its save alot of time of the reviewer like leam and the senior dev 

## Current workaround
They write a short PR description, and sometimes none at all. The reviewer reads the whole diff and guesses which parts are risky. Linters and CI catch small things like formatting, but not logic mistakes. Sometimes the PR just sits and waits for someone to have time

## Claims

## The switch
What they’d fire: when dev cpush the code and create a PR then reading the raw diff file by file, then pinging the author in chat to explain it.

Push: big PRs and AI-assisted changes arrive faster than people can review them, and descriptions are short.

Pull: open a PR and immediately see what changed and which parts are risky.

Anxiety: noisy or wrong bot comments, and private code going to an AI provider.

Habit: teams already review in GitHub’s Files tab, and a new tool is one more thing to read. and it shown more bugs 

The one worry onboarding must remove: Will this bury my PRs in wrong comments and send my private code somewhere I don’t control

## The core flow
## 3. The core flow

Today (before your product):
1. The reviewer is notified of a PR, opens it, and sees a short description and 14 changed files. They can't tell what changed or why. (the moment it hurts)
2. They open the Files tab and read the diffs one file at a time.
3. They try to guess which files are risky and which are just noise.
4. They message the author in chat to ask what the change does.
5. They wait for the author to reply.
6. They go back to the diff, check the risky parts, and leave comments.
The review ends late, and sometimes with a quick approve because the reviewer ran out of time. (where it ends today)

With my product:
1. The reviewer is notified of a PR and opens it. (the moment it hurts, same as today)
2. The product has already posted one summary comment on the PR: what changed, a short note per file, and the risky areas. The reviewer reads it.
3. The product lists the two or three files most worth checking first, so the reviewer knows where to look.
4. The reviewer checks those parts in the diff and approves or comments, without asking the author to explain. (the job done: understood the change and checked the risky parts quickly)

What must not happen:
the summary is wrong or misleading, for example calling a risky change safe, so the reviewer trusts it and misses a real bug.

## Onboarding

First value (the moment it first does the job for them):
A summary comment appears on one of their own real PRs: what changed, a note per file, and the files most worth checking.

The smallest commitment we ask for:
Install the GitHub App on ONE repository they choose (not the whole organization).

The worry it removes (from section 2):
"Will this bury my PRs in wrong comments and send my private code somewhere I don't control?"

From opening the link to the first value:
1. They open the link and land on a page that shows a sample summary on a public PR, with no login. They can see exactly what the comment looks like: one short comment, labeled as AI-generated, no inline spam.
   removes: the fear of noisy or wrong comments.
2. They click "Install on GitHub". GitHub's own screen shows exactly which permissions we ask for, and they pick one repository. A short note on our page says what code is sent for analysis and that we don't keep it. [GUESS: confirm this matches what you actually build]
   removes: the fear of giving access to private code.
3. Right after install, the product summarizes the most recent open PR in that repo, and posts the comment. They don't have to wait for a new PR. They open the PR and see the summary. (first value)

Login: not in v1 as a separate account. The GitHub install is the only sign-in. We add our own login after step 3 only if we need a dashboard, because nothing before the first summary needs one.

What we don't ask on day one:
Billing details, inviting teammates, installing on other repos, config files, review rules, Slack or other integrations, and their role or company size.

What we ask later, and when:
- "Was this summary useful?" (thumbs up or down on the comment) after the first summary.
- "Add more repositories?" after a thumbs up on at least one summary.
- "Choose a plan" after they reach the free usage cap.
- "Customize what we focus on" after a thumbs down, since that is the moment they care about changing the output.

## v1
Does (one person finishes the one job):
A reviewer opens a PR and finds one AI-generated summary comment already there. It says what changed, gives a short note per file, and names the 2-3 files most worth checking first. The reviewer checks those parts and approves or comments without asking the author to explain.
To make that work, v1 has to:
- install on one GitHub repo as a GitHub App
- fetch the PR diff and skip noise (lockfiles, generated files, images)
- summarize each file, then combine into one PR summary
- post one comment, labeled as AI-generated, and update that same comment when new commits are pushed
- log each review run (repo, PR number, commit SHA, summary) so I can see what it did

Doesn't (parked, not forgotten):
- inline line-by-line review comments
- chat replies and follow-up questions to the bot
- linters, security scanning, or test generation
- GitLab and Bitbucket support
- team dashboards and analytics
- custom review rules or a config file
- billing and paid plans
- whole-codebase indexing for cross-file context

Nice to have (only after the must haves work):
- a "changes since your last review" note when new commits are pushed
- thumbs up/down on the summary comment
- a risk label (low / medium / high) per file
- a free usage cap per repo so a spike can't drain API credits

How I'll know it worked (what they do again, not what they say):
- After the first summary, they keep the app installed for at least 2 weeks. [GUESS: threshold]
- The next PRs on that repo still get summaries, and the team does not turn the bot off or mute it.
- They add a second repository without being asked to. 
- A reviewer opens the summary on a new PR on their own, instead of going straight to the Files tab
What would say it did NOT work: the app is uninstalled within a week, or reviewers still message the author to ask what the PR does.

## The riskiest guess
If this is false, the product is pointless:
Reviewers can't tell what a large PR changes, or where the risk is, from the PR description and diff alone, and a short summary would fix that. If most PRs already have good descriptions, or reviewers are slow for another reason (waiting on CI, no time, unclear ownership), a summary doesn't help and the product has no job to do.

Thirty-minute check, no code, and what happened:
The check (30 minutes, timeboxed):
1. (10 min) Open the last 10 PRs in one repo, yours or a public one. For each, note the number of changed files and whether the description explains what changed in more than two sentences.
2. (10 min) Pick the biggest PR. Paste its diff into Claude by hand and ask for the kind of summary my product would post. Read it and judge: is it accurate, and does it tell me what to check first?
3. (10 min) Show that summary to one real reviewer or the PR's author. Ask: "Is this accurate? Would it have saved you time on this PR? What was actually slow about reviewing it?"

What I'm looking for:
- Supports the assumption: most big PRs have thin descriptions, the summary is accurate, and the person says it would have saved real time.
- Contradicts it: descriptions are mostly fine, the summary has errors, or the person says the slow part was something else.

What happened: [FILL IN after you run it]
- PRs checked: [n]; descriptions longer than two sentences: [n of 10]
- Was the summary accurate? [yes / partly / no, and what was wrong]
- What the reviewer said, in one sentence: [their words]
- My decision: [keep going / change the problem / change the product, and why]

## Milestones

1. I can take one real PR diff (14 files, no code of mine around it) and get a summary that a reviewer says is accurate and tells them what to check first.
2. I can receive a webhook when a PR is opened on my test repo, verify its signature, and fetch the changed files and their diffs from GitHub.
3. I can run that diff through the summarizer automatically (skipping lockfiles and generated files) and get one combined PR summary.
4. I can post that summary as one comment on the PR, labeled as AI-generated, and update the same comment when a new commit is pushed instead of adding a second one.
5. I can install the app on one repository through GitHub's install screen, and a summary appears on that repo's latest open PR without me touching anything.
Last: I can close it, reopen it, and my data is still there.
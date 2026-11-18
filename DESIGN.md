# DESIGN.md
Read this before building or changing any screen. If a choice isn't covered here, ask me instead of guessing.

## 1. The feeling, in labels
The bot comment sits in the same comment box as a human comment, with only a small "Bot" tag, so the AI summary feels like part of GitHub.
Branch names like feature/queue are in monospace on a light blue chip, so they stand out from the sentence and are read in one look.
The green "Open" pill under the title is the biggest coloured thing on the page, so the PR status is read first.
Each tab has an icon, a name and a count (Commits 1, Files changed 14), so you know how much is inside before you click.
"+256 −7" with small green boxes sits at the right of the tabs, so you see how big the change is without opening the diff.

## 2. References, one per component
PR comment preview: CodeRabbit's "Summary by CodeRabbit" comment on a GitHub PR Take: plain GitHub markdown, one heading, short bullet points, sits in the normal comment box. Ignore: the "Explain Change" button, emoji reactions, the "..." menu.

Dashboard run list: GitHub Actions workflow runs list (Actions tab of any repo) Take: one row per run, title in bold, small grey meta line under it, status on the right. Ignore: the coloured status icons and the filter bar.

Review diff with AI notes: GitHub "Files changed" tab in split view Take: side-by-side diff, line numbers in grey, soft green/red rows, file header bar. Ignore: the comment thread UI and the "Viewed" checkbox.

Layers sidebar: Linear's sidebar Take: numbered items, small chip for counts, selected item gets a white background and thin border. Ignore: icons, keyboard shortcuts, team switcher.

## 3. Type and colour
28 px bold: page title (one per screen)
18 px semibold: section titles inside a page
15 px regular: body text and buttons
13 px: meta info, tags, small notes

Colours: 
#1F2328 on 
#FFFFFF · accent 
#1F6FEB, only on the main action of each screen · errors 
#CF222E
## 4. Screens
Connected: repo is linked. Top to bottom: repo name, latest PR, button. Main action: "Open the pull request" → PR on GitHub
Empty: "No open PRs yet." · Loading: "Reading your PR..." · Error: "Couldn't read this PR. Nothing posted." · Done: "Summary posted."

Dashboard: all reviewed PRs. Top to bottom: repo name, reviews used, list of PRs. Main action: "View summary" → Review
Empty: "No PRs reviewed yet." · Loading: "Loading PRs..." · Error: "Couldn't load. Your PRs are fine." · Done: list, newest first

Review: one PR, layer by layer. Top to bottom: PR title, layers on left, summary and diff on right. Main action: "Open on GitHub" → PR on GitHub
Empty: "Nothing to summarize." · Loading: "Reading 14 files..." · Error: "Couldn't load this review." · Done: overview first

## 5. The first screen's words
Headline: Know what a pull request does before you open the diff. Under it: We read every pull request and post a short summary on it, with the files to check first. For developers who review a lot of PRs. Button: Connect a GitHub repo

## 6. Principles
One main action per screen. Only that button uses the accent colour.
The summary on GitHub uses plain GitHub markdown, no custom styling, so it looks like a normal comment.
Anything the AI wrote says it can be wrong, right next to it.
Errors say what happened and what is safe, then give one way to retry. No error codes.
Failed runs never post anything on GitHub, and the screen says so.
File names, PR numbers and commit ids are always in monospace.
Check every screen at phone width before calling it done.

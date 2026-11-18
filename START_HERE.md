# Start in your own terminal

1. Download and unzip these files into your own product folder. Keep the filenames. Check REVIEW_NOTES.md: a saved draft is not an approval.
2. On Mac, open Terminal from Applications → Utilities. On Windows, open Windows Terminal or PowerShell from Start.
3. Type cd followed by your project folder path in quotes, then press Enter. Example: cd "your-project-folder". Replace the example with your actual folder.
4. Choose one coding agent. Install and sign in using its official guide: Codex https://developers.openai.com/codex/cli or Claude Code https://code.claude.com/docs/en/quickstart. Use your own account; never share a key, password or session file with the team tool.
5. In that folder, run codex or claude. Paste the prompt below into that agent, not into your shell.

## First prompt
Read AGENTS.md, PRODUCT.md and DESIGN.md first. Explain what each file says and flag anything missing or not approved in REVIEW_NOTES.md. Do not invent my answers. Plan milestone 1 around the riskiest part of PRODUCT.md. Tell me your plan in 2–3 sentences and wait for my yes before writing code. Work locally. Do not deploy or add paid services. Keep PLAN.md and PROGRESS.md updated.

## After you approve the plan
Build only the approved milestone. Test it on real input. Show the actual test output and a phone-width screenshot. If a check fails, explain what failed and fix it. Do not claim success without checking. Do not deploy.

## Daily token evidence
Use the coding agent's own usage report to find the day's token count. Upload a readable screenshot in Daily coding tokens. ATLAS uses the number shown in the screenshot; typed numbers and terminal activity alone do not earn points. If your report only shows cumulative totals, ask for guidance rather than guessing a daily count.

## Optional connection
The app's Connect my terminal to ATLAS panel lets you pair this project voluntarily and report progress. It does not grant access to your Codex or Claude account and does not automatically verify your provider's token count.

# AGENTS.md

## 1. How the product works
IInterface: React (Vite) web app. Screens from DESIGN.md: Connected, Dashboard, Review. The summary itself lives as a comment on the GitHub PR. Business logic: FastAPI (Python). Gets the GitHub webhook when a PR is opened or updated, reads the diff, asks the AI for a summary, posts or updates one comment. Database: Postgres (Neon free tier). Tables: repos, runs, summaries, usage. Approved outside services: GitHub App (webhooks + PR comments), Claude API (summary)/also we can use free like gemini-embadding-001 , Neon (database), Render (hosting). Nothing else without asking me.

## 2. Working with the agent
Plan and approval: Write the plan first. Wait for my "ok" before writing code. One small feature at a time. 
Tests and screenshots: Add a test for every backend change. For every screen change, send a screenshot at desktop and phone width. PLAN.md and 
PROGRESS.md: PLAN.md = what we will build next. PROGRESS.md = what is done, what broke, what is next. Update both at the end of every task.

## 3. Ship it
Local checks: Tests pass, lint passes, app runs locally with docker compose before any push. Own GitHub repository: All code goes to my repo Ra-vi-chilwal/pr-summary. No other repo. Explicit deployment approval: Never deploy without me saying "deploy". Tell me what will change first. Secrets stay
 server-side: GitHub App key, Claude API key and DB URL only in backend env vars. Never in frontend code, never in git, never in logs.

## 4. Connecting the AI

Allowed: read the PR diff, write a summary, post or edit its own one comment on that PR.
Not allowed: approve, merge, close or push to a PR. No comments anywhere else. No reading other repos. Reply, call and monthly spend caps:
One comment per PR, edited on new commits (not a new comment each time).
Max 1 AI call per push. Skip PRs with more than 100 files or only lockfiles.
50 reviews per repo per month. Stop at $10 total API spend per month and tell me. Uncertainty, privacy and failure handling:
If the AI is not sure, it says so ("Could not tell what this file does").
 Every summary ends with "Written by AI. It can be wrong."
Code is only sent to Claude for the summary. We don't store the diff, only the summary.
If anything fails, post nothing on GitHub and show "Failed, nothing posted" on the dashboard.

import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Me, RunDetail, RunInfo, RunList } from "./api";
import { SIGNED_IN, SIGNED_OUT, mockApi, renderAt } from "./testUtils";

const NOW = new Date().toISOString();

function runInfo(o: Partial<RunInfo> = {}): RunInfo {
  return {
    id: 5,
    title: "Add retry to webhook",
    status: "done",
    message: "Summary ready.",
    files_total: 3,
    files_kept: 2,
    created_at: NOW,
    summary_id: 9,
    ...o,
  };
}

const LIST: RunList = {
  runs: [runInfo(), runInfo({ id: 4, title: "", status: "failed", message: "Failed, nothing posted.", summary_id: null })],
  runs_this_month: 2,
  spend_this_month_usd: 0.12,
  spend_cap_usd: 10,
};

const DETAIL: RunDetail = {
  run: runInfo(),
  result: {
    overview: "Retries failed webhook deliveries.",
    files: [
      { path: "src/retry.py", note: "New retry loop.", unsure: false },
      { path: "src/odd.cfg", note: "", unsure: true },
    ],
    check_first: [{ path: "src/retry.py", reason: "A failed attempt could be counted twice." }],
    skipped: [{ path: "package-lock.json", reason: "lockfile" }],
  },
  comment_markdown: "## PR summary\n---\nWritten by AI. It can be wrong.",
  model: "gemini-3.8-flash",
  verdict_accurate: null,
};

const CONNECTED: Me = {
  ...SIGNED_IN,
  installations: [
    {
      installation_id: 42,
      account_login: "Ra-vi-chilwal",
      account_type: "User",
      repo_count: 2,
      manage_url: "https://github.com/settings/installations/42",
    },
  ],
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Get started and the sidebar", () => {
  it("shows the headline, steps and a sign-in link when signed out", async () => {
    mockApi({ "GET /api/auth/me": SIGNED_OUT });
    renderAt("/");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "Know what a pull request does before you open the diff.",
    );
    expect(screen.getByText("Install on one repository")).toBeTruthy();
    expect(await screen.findByRole("link", { name: "Create an account" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Sign in" })).toBeTruthy();
    expect(screen.getByText("No GitHub account connected")).toBeTruthy();
  });

  it("shows the account, connection and log out when signed in and connected", async () => {
    mockApi({ "GET /api/auth/me": CONNECTED });
    renderAt("/");
    expect(await screen.findByText("Ravi Chilwal")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Log out" })).toBeTruthy();
    expect(screen.getByText("2 repositories connected")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Manage" }).getAttribute("href")).toBe(
      "https://github.com/settings/installations/42",
    );
  });
});

describe("Protected routes", () => {
  it("does not show the dashboard to signed-out visitors", async () => {
    mockApi({ "GET /api/auth/me": SIGNED_OUT });
    renderAt("/dashboard");
    await waitFor(() => expect(screen.queryByRole("heading", { name: "Dashboard" })).toBeNull());
  });
});

describe("Dashboard", () => {
  it("lists summaries newest first with usage; failed runs say nothing was posted", async () => {
    mockApi({ "GET /api/auth/me": SIGNED_IN, "GET /api/runs": LIST });
    renderAt("/dashboard");
    await screen.findByText("Add retry to webhook");
    expect(screen.getByText("$0.12")).toBeTruthy();
    expect(screen.getByText("Failed, nothing posted")).toBeTruthy();
    expect(screen.getByText("Untitled diff")).toBeTruthy();
    expect(screen.getByRole("link", { name: /View summary: Add retry/ }).getAttribute("href")).toBe("/review?run=5");
  });

  it("invites the user to connect GitHub when nothing is connected", async () => {
    mockApi({ "GET /api/auth/me": SIGNED_IN, "GET /api/runs": { ...LIST, runs: [] } });
    renderAt("/dashboard");
    await screen.findByText("Connect GitHub to summarize your pull requests");
    expect(screen.getByRole("link", { name: "Connect GitHub" }).getAttribute("href")).toBe("/api/github/install");
    expect(await screen.findByText("No summaries yet")).toBeTruthy();
  });

  it("lists repos with a Private badge, then open PRs, then summarizes one", async () => {
    mockApi({
      "GET /api/auth/me": CONNECTED,
      "GET /api/runs": LIST,
      "GET /api/github/repos": {
        repos: [
          { full_name: "Ra-vi-chilwal/secret", owner: "Ra-vi-chilwal", name: "secret", private: true, installation_id: 42, updated_at: NOW },
        ],
      },
      "GET /api/github/repos/Ra-vi-chilwal/secret/pulls": {
        pulls: [{ number: 3, title: "Fix login", author: "ravi", updated_at: NOW, draft: false, html_url: "https://github.com/x" }],
      },
      "POST /api/github/repos/Ra-vi-chilwal/secret/pulls/3/summarize": {
        run_id: 5, status: "done", message: "ok", files_total: 1, files_kept: 1, skipped: [],
        summary_id: 9, comment_markdown: "x", diff: "diff --git a/a b/a\n",
      },
      "GET /api/runs/5": DETAIL,
    }); // prettier-ignore
    renderAt("/dashboard");
    const repo = await screen.findByText("Ra-vi-chilwal/secret");
    expect(screen.getByText("Private")).toBeTruthy();
    fireEvent.click(repo);
    fireEvent.click(await screen.findByText("Fix login"));
    await screen.findByText("Retries failed webhook deliveries.");
  });

  it("shows a safe error with one retry", async () => {
    mockApi({ "GET /api/auth/me": SIGNED_IN, "GET /api/runs": [new Error("down"), LIST] });
    renderAt("/dashboard");
    await screen.findByText("Couldn't load your summaries. Your PRs are fine.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByText("Add retry to webhook");
  });
});

describe("Summary page", () => {
  it("shows overview, coverage with the skipped file, and the unsure note", async () => {
    mockApi({ "GET /api/auth/me": SIGNED_IN, "GET /api/runs/5": DETAIL });
    renderAt("/review/5");
    await screen.findByText("Retries failed webhook deliveries.");
    expect(screen.getByText("package-lock.json")).toBeTruthy();
    expect(screen.getByRole("img", { name: "2 of 3 files read" })).toBeTruthy();
    expect(screen.getByText("Could not tell what this file does.")).toBeTruthy();
    expect(screen.getAllByText(/Written by AI. It can be wrong./).length).toBeGreaterThan(0);
  });

  it("loads from the static-host friendly link /review?run=5", async () => {
    mockApi({ "GET /api/auth/me": SIGNED_IN, "GET /api/runs/5": DETAIL });
    renderAt("/review?run=5");
    await screen.findByText("Retries failed webhook deliveries.");
  });

  it("opens a file: check-first reason, AI note, and says the diff isn't stored", async () => {
    mockApi({ "GET /api/auth/me": SIGNED_IN, "GET /api/runs/5": DETAIL });
    renderAt("/review/5");
    await screen.findByText("Retries failed webhook deliveries.");
    fireEvent.click(screen.getAllByRole("button", { name: /src\/retry.py/ })[0]);
    expect(screen.getByText("A failed attempt could be counted twice.")).toBeTruthy();
    expect(screen.getByText("New retry loop.")).toBeTruthy();
    expect(screen.getByText(/We don't store diffs/)).toBeTruthy();
  });

  it("shows the side-by-side diff for a PR summarized in this tab", async () => {
    const diff = ["diff --git a/src/retry.py b/src/retry.py", "--- a/src/retry.py", "+++ b/src/retry.py", "@@ -1 +1 @@", "-tries = 1", "+tries = 5", ""].join("\n");
    mockApi({
      "GET /api/auth/me": SIGNED_IN,
      "POST /api/summaries": {
        run_id: 5, status: "done", message: "Summary ready.", files_total: 1, files_kept: 1,
        skipped: [], summary_id: 9, comment_markdown: "x",
      },
      "GET /api/runs/5": DETAIL,
    }); // prettier-ignore
    renderAt("/try");
    fireEvent.change(screen.getByLabelText("PR link or diff"), { target: { value: diff } });
    fireEvent.click(screen.getByRole("button", { name: "Summarize" }));
    fireEvent.click(await screen.findByRole("link", { name: /Open full summary/ }));
    await screen.findByText("Retries failed webhook deliveries.");
    fireEvent.click(screen.getAllByRole("button", { name: /src\/retry.py/ })[0]);
    expect(screen.getByText("tries = 1").className).toBe("del");
    expect(screen.getByText("tries = 5").className).toBe("add");
  });

  it("explains a failed run instead of showing a summary", async () => {
    mockApi({
      "GET /api/auth/me": SIGNED_IN,
      "GET /api/runs/5": { ...DETAIL, run: runInfo({ status: "failed", message: "Failed, nothing posted.", summary_id: null }), result: null, comment_markdown: null },
    });
    renderAt("/review/5");
    await screen.findByText("This run failed, so nothing was posted");
  });

  it("shows a safe error", async () => {
    mockApi({ "GET /api/auth/me": SIGNED_IN, "GET /api/runs/5": new Error("down") });
    renderAt("/review/5");
    await screen.findByText("Couldn't load this summary. Nothing was changed on GitHub.");
  });
});

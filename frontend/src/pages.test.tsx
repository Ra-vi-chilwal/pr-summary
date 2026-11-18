import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { RunDetail, RunInfo, RunList } from "./api";
import { mockFetch, renderAt } from "./testUtils";

const NOW = new Date().toISOString();

function runInfo(o: Partial<RunInfo>): RunInfo {
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
  runs: [
    runInfo({}),
    runInfo({ id: 4, title: "", status: "failed", message: "Failed, nothing posted.", summary_id: null }),
  ],
  runs_this_month: 2,
  spend_this_month_usd: 0.12,
  spend_cap_usd: 10,
};

const DETAIL: RunDetail = {
  run: runInfo({}),
  result: {
    overview: "Retries failed webhook deliveries.",
    files: [
      { path: "src/retry.py", note: "New retry loop.", unsure: false },
      { path: "src/odd.cfg", note: "", unsure: true },
    ],
    check_first: [{ path: "src/retry.py", reason: "A failed attempt could be counted twice." }],
  },
  comment_markdown: "## PR summary\n---\nWritten by AI. It can be wrong.",
  model: "claude-opus-5-5",
  verdict_accurate: null,
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Shell and Get started", () => {
  it("shows the DESIGN.md headline and the three steps, with connect not yet available", () => {
    renderAt("/");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "Know what a pull request does before you open the diff.",
    );
    expect(screen.getByText("Install on one repository")).toBeTruthy();
    const connect = screen.getByRole("button", { name: "Connect a GitHub repo" }) as HTMLButtonElement;
    expect(connect.disabled).toBe(true);
    expect(screen.getByRole("link", { name: /Dashboard/ })).toBeTruthy();
  });
});

describe("Dashboard", () => {
  it("lists runs newest first with usage, and failed runs say nothing was posted", async () => {
    mockFetch(LIST);
    renderAt("/dashboard");
    expect(screen.getByText("Loading PRs...")).toBeTruthy();
    await waitFor(() => screen.getByText("Add retry to webhook"));
    expect(screen.getByText(/2 runs this month · AI spend \$0.12 of \$10/)).toBeTruthy();
    expect(screen.getByText("Failed, nothing posted")).toBeTruthy();
    expect(screen.getByText("Untitled diff")).toBeTruthy();
    expect(screen.getByRole("link", { name: "View summary" }).getAttribute("href")).toBe("/review/5");
  });

  it("shows the empty state", async () => {
    mockFetch({ ...LIST, runs: [], runs_this_month: 0 });
    renderAt("/dashboard");
    await waitFor(() => screen.getByText("No PRs reviewed yet."));
  });

  it("shows a safe error with one retry", async () => {
    mockFetch(new Error("down"), LIST);
    renderAt("/dashboard");
    await waitFor(() => screen.getByText("Couldn't load. Your PRs are fine."));
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => screen.getByText("Add retry to webhook"));
  });
});

describe("Review", () => {
  it("shows the overview, then a file with its AI note; says the diff isn't stored", async () => {
    mockFetch(DETAIL);
    renderAt("/review/5");
    await waitFor(() => screen.getByText("Retries failed webhook deliveries."));
    expect(screen.getAllByText("Written by AI. It can be wrong.").length).toBeGreaterThan(0);
    expect(screen.getByText("Could not tell what this file does.")).toBeTruthy();

    fireEvent.click(screen.getAllByRole("button", { name: /src\/retry.py/ })[0]);
    expect(screen.getByText("A failed attempt could be counted twice.")).toBeTruthy();
    expect(screen.getByText("New retry loop.")).toBeTruthy();
    expect(screen.getByText(/The diff isn.t stored/)).toBeTruthy();
  });

  it("shows the side-by-side diff for a diff summarized in this tab", async () => {
    const diff = [
      "diff --git a/src/retry.py b/src/retry.py",
      "--- a/src/retry.py",
      "+++ b/src/retry.py",
      "@@ -1 +1 @@",
      "-tries = 1",
      "+tries = 5",
      "",
    ].join("\n");
    mockFetch(
      {
        run_id: 5, status: "done", message: "Summary ready.", files_total: 1, files_kept: 1,
        skipped: [], summary_id: 9, comment_markdown: "x",
      },
      DETAIL,
    ); // prettier-ignore
    renderAt("/try");
    fireEvent.change(screen.getByPlaceholderText(/github.com/), { target: { value: diff } });
    fireEvent.click(screen.getByRole("button", { name: "Summarize" }));
    await waitFor(() => screen.getByRole("link", { name: "Open the review with the diff" }));
    fireEvent.click(screen.getByRole("link", { name: "Open the review with the diff" }));
    await waitFor(() => screen.getByText("Retries failed webhook deliveries."));

    fireEvent.click(screen.getAllByRole("button", { name: /src\/retry.py/ })[0]);
    expect(screen.getByText("tries = 1").className).toBe("del");
    expect(screen.getByText("tries = 5").className).toBe("add");
    expect(screen.queryByText(/The diff isn.t stored/)).toBeNull();
  });

  it("shows a skipped run's message instead of a summary", async () => {
    mockFetch({
      ...DETAIL,
      run: runInfo({ status: "skipped", message: "Nothing to summarize.", summary_id: null }),
      result: null,
      comment_markdown: null,
    });
    renderAt("/review/5");
    await waitFor(() => screen.getByText("Nothing to summarize."));
  });

  it("shows a safe error", async () => {
    mockFetch(new Error("down"));
    renderAt("/review/5");
    await waitFor(() => screen.getByText("Couldn't load this review."));
  });
});

import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { countFiles, isPrLink, type SummarizeResult } from "./api";
import { SIGNED_IN, callsTo, mockApi, renderAt } from "./testUtils";

const DIFF = "diff --git a/a.py b/a.py\n+x\ndiff --git a/b.py b/b.py\n+y\n";
const LINK = "https://github.com/Ra-vi-chilwal/trustRush-fastAPI/pull/1";

function result(overrides: Partial<SummarizeResult> = {}): SummarizeResult {
  return {
    run_id: 7,
    status: "done",
    message: "Summary ready.",
    files_total: 2,
    files_kept: 2,
    skipped: [],
    summary_id: 3,
    comment_markdown: "## PR summary\n\n---\nWritten by AI. It can be wrong.",
    ...overrides,
  };
}

function pasteAndSubmit(text = DIFF) {
  fireEvent.change(screen.getByLabelText("PR link or diff"), { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "Summarize" }));
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Try a diff", () => {
  it("is public and starts with Summarize disabled", async () => {
    mockApi();
    renderAt("/try");
    expect(screen.getByRole("heading", { level: 1, name: "Try a diff" })).toBeTruthy();
    expect((screen.getByRole("button", { name: "Summarize" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("shows a skeleton with the file count, then the comment and AI warning", async () => {
    const fetchFn = mockApi({ "POST /api/summaries": result() });
    renderAt("/try");
    pasteAndSubmit();
    expect(screen.getByText("Reading 2 files...")).toBeTruthy();
    await waitFor(() => screen.getByTestId("comment"));
    expect(screen.getByTestId("comment").textContent).toContain("Written by AI. It can be wrong.");
    expect(callsTo(fetchFn, "POST /api/summaries")).toEqual([{ diff: DIFF, title: "" }]);
  });

  it("asks signed-out users to sign in to keep the summary", async () => {
    mockApi({ "POST /api/summaries": result() });
    renderAt("/try");
    pasteAndSubmit();
    const link = await screen.findByRole("link", { name: /Sign in to keep this summary/ });
    expect(link.getAttribute("href")).toBe("/login?next=%2Freview%3Frun%3D7");
  });

  it("links signed-in users to the full summary", async () => {
    mockApi({ "GET /api/auth/me": SIGNED_IN, "POST /api/summaries": result() });
    renderAt("/try");
    pasteAndSubmit();
    const link = await screen.findByRole("link", { name: /Open full summary/ });
    expect(link.getAttribute("href")).toBe("/review?run=7");
  });

  it("shows 'Failed, nothing posted.' when the run fails", async () => {
    mockApi({
      "POST /api/summaries": result({ status: "failed", message: "Failed, nothing posted.", comment_markdown: null, summary_id: null }),
    });
    renderAt("/try");
    pasteAndSubmit();
    await screen.findByText("Failed, nothing posted.");
    expect(screen.queryByTestId("comment")).toBeNull();
  });

  it("explains skipped lockfile-only diffs", async () => {
    mockApi({
      "POST /api/summaries": result({
        status: "skipped",
        message: "Nothing to summarize. Only lockfiles, generated files or images changed.",
        comment_markdown: null,
        summary_id: null,
        skipped: [{ path: "package-lock.json", reason: "lockfile" }],
      }),
    });
    renderAt("/try");
    pasteAndSubmit();
    await screen.findByText(/^Nothing to summarize/);
    expect(screen.getByText("package-lock.json")).toBeTruthy();
  });

  it("shows a safe error with one retry when the server can't be reached", async () => {
    mockApi({ "POST /api/summaries": [new Error("network"), result()] });
    renderAt("/try");
    pasteAndSubmit();
    await screen.findByText("Couldn't reach the server. Nothing was posted.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => screen.getByTestId("comment"));
  });

  it("saves the reviewer verdict", async () => {
    const fetchFn = mockApi({ "POST /api/summaries": result(), "POST /api/summaries/3/verdict": { ok: true } });
    renderAt("/try");
    pasteAndSubmit();
    await waitFor(() => screen.getByTestId("comment"));
    const save = screen.getByRole("button", { name: "Save verdict" }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    fireEvent.click(screen.getByLabelText("partly"));
    fireEvent.change(screen.getByLabelText(/What was actually slow/), { target: { value: "Waiting on CI" } });
    fireEvent.click(save);
    await screen.findByText("Verdict saved. Thank you.");
    expect(callsTo(fetchFn, "POST /api/summaries/3/verdict")).toEqual([
      { accurate: "partly", saved_time: null, note: "Waiting on CI" },
    ]);
  });

  it("copies the comment and confirms with a toast", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    mockApi({ "POST /api/summaries": result() });
    renderAt("/try");
    pasteAndSubmit();
    await waitFor(() => screen.getByTestId("comment"));
    fireEvent.click(screen.getByRole("button", { name: /Copy comment/ }));
    await screen.findByText("Comment copied.");
    expect(writeText).toHaveBeenCalledWith(result().comment_markdown);
  });
});

describe("pasting a PR link", () => {
  it("sends the link and fills the title from the PR", async () => {
    const fetchFn = mockApi({ "POST /api/summaries": result({ diff: DIFF, title: "chnage in the branch" }) });
    renderAt("/try");
    pasteAndSubmit(LINK);
    expect(screen.getByText("Getting the PR from GitHub and reading it...")).toBeTruthy();
    await waitFor(() => screen.getByTestId("comment"));
    expect(callsTo(fetchFn, "POST /api/summaries")[0].diff).toBe(LINK);
    expect((screen.getByLabelText(/^Title/) as HTMLInputElement).value).toBe("chnage in the branch");
  });

  it("shows the backend's message when the PR can't be read", async () => {
    mockApi({
      "POST /api/summaries": { status: 422, body: { detail: "Couldn't read this PR. Nothing was sent to the AI." } },
    });
    renderAt("/try");
    pasteAndSubmit("https://github.com/a/private-repo/pull/3");
    await screen.findByText("Couldn't read this PR. Nothing was sent to the AI.");
  });
});

describe("helpers", () => {
  it("isPrLink recognizes PR links but not diffs", () => {
    expect(isPrLink(" https://github.com/a/b/pull/12/files ")).toBe(true);
    expect(isPrLink("https://patch-diff.githubusercontent.com/raw/a/b/pull/1.diff")).toBe(true);
    expect(isPrLink("diff --git a/x b/x")).toBe(false);
    expect(isPrLink("https://example.com/a/b/pull/1")).toBe(false);
  });

  it("countFiles counts diff --git headers", () => {
    expect(countFiles(DIFF)).toBe(2);
    expect(countFiles("")).toBe(0);
  });
});

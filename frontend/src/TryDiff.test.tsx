import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mockFetch, renderAt } from "./testUtils";
import { countFiles, type SummarizeResult } from "./api";

const DIFF = "diff --git a/a.py b/a.py\n+x\ndiff --git a/b.py b/b.py\n+y\n";

function result(overrides: Partial<SummarizeResult>): SummarizeResult {
  return {
    run_id: 7,
    status: "done",
    message: "Summary ready. Nothing was posted to GitHub (dev mode).",
    files_total: 2,
    files_kept: 2,
    skipped: [],
    summary_id: 3,
    comment_markdown: "## PR summary\n\n---\nWritten by AI. It can be wrong.",
    ...overrides,
  };
}

function pasteAndSubmit(text = DIFF) {
  fireEvent.change(screen.getByPlaceholderText(/diff --git/), { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "Summarize" }));
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("TryDiff", () => {
  it("starts empty with Summarize disabled", () => {
    renderAt("/try");
    expect(screen.getByText("Paste a diff to see the summary.")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Summarize" }) as HTMLButtonElement).disabled).toBe(
      true,
    );
  });

  it("shows the file count while loading, then the comment with the AI warning", async () => {
    const fetchFn = mockFetch(result({}));
    renderAt("/try");
    pasteAndSubmit();
    expect(screen.getByText("Reading 2 files...")).toBeTruthy();
    await waitFor(() => expect(screen.getByTestId("comment")).toBeTruthy());
    expect(screen.getByTestId("comment").textContent).toContain("Written by AI. It can be wrong.");
    expect(screen.getAllByText("Written by AI. It can be wrong.").length).toBeGreaterThan(0);
    const [url, init] = fetchFn.mock.calls[0];
    expect(url).toBe("/api/dev/summaries");
    expect(JSON.parse(init.body)).toEqual({ diff: DIFF, title: "" });
  });

  it("shows 'Failed, nothing posted.' when the run fails", async () => {
    mockFetch(result({ status: "failed", message: "Failed, nothing posted.", comment_markdown: null, summary_id: null }));
    renderAt("/try");
    pasteAndSubmit();
    await waitFor(() => expect(screen.getByText("Failed, nothing posted.")).toBeTruthy());
    expect(screen.queryByTestId("comment")).toBeNull();
  });

  it("shows the skip message for lockfile-only diffs", async () => {
    mockFetch(
      result({
        status: "skipped",
        message: "Nothing to summarize. Only lockfiles, generated files or images changed.",
        comment_markdown: null,
        summary_id: null,
        skipped: [{ path: "package-lock.json", reason: "lockfile" }],
      }),
    );
    renderAt("/try");
    pasteAndSubmit();
    await waitFor(() => expect(screen.getByText(/^Nothing to summarize/)).toBeTruthy());
    expect(screen.getByText(/package-lock.json/)).toBeTruthy();
  });

  it("shows a safe error with one retry when the server can't be reached", async () => {
    mockFetch(new Error("network"), result({}));
    renderAt("/try");
    pasteAndSubmit();
    await waitFor(() =>
      expect(screen.getByText("Couldn't reach the server. Nothing was posted.")).toBeTruthy(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByTestId("comment")).toBeTruthy());
  });

  it("saves the reviewer verdict", async () => {
    const fetchFn = mockFetch(result({}), { ok: true });
    renderAt("/try");
    pasteAndSubmit();
    await waitFor(() => screen.getByTestId("comment"));
    const save = screen.getByRole("button", { name: "Save verdict" }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    fireEvent.click(screen.getByLabelText("partly"));
    fireEvent.change(screen.getByLabelText(/What was actually slow/), {
      target: { value: "Waiting on CI" },
    });
    fireEvent.click(save);
    await waitFor(() => expect(screen.getByText("Verdict saved. Thank you.")).toBeTruthy());
    const [url, init] = fetchFn.mock.calls[1];
    expect(url).toBe("/api/dev/summaries/3/verdict");
    expect(JSON.parse(init.body)).toEqual({ accurate: "partly", saved_time: null, note: "Waiting on CI" });
  });
});

describe("countFiles", () => {
  it("counts diff --git headers", () => {
    expect(countFiles(DIFF)).toBe(2);
    expect(countFiles("")).toBe(0);
  });
});

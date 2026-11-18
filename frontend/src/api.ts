export type RunStatus = "done" | "skipped" | "failed" | "capped" | "running";

export interface SummarizeResult {
  run_id: number;
  status: RunStatus;
  message: string;
  files_total: number;
  files_kept: number;
  skipped: { path: string; reason: string }[];
  summary_id: number | null;
  comment_markdown: string | null;
  /** Set only when a PR link was pasted: the diff GitHub returned (never stored). */
  diff?: string | null;
  title?: string;
}

export interface Verdict {
  accurate: "yes" | "partly" | "no";
  saved_time: boolean | null;
  note: string;
}

export interface RunInfo {
  id: number;
  title: string;
  status: RunStatus;
  message: string;
  files_total: number;
  files_kept: number;
  created_at: string;
  summary_id: number | null;
}

export interface RunList {
  runs: RunInfo[];
  runs_this_month: number;
  spend_this_month_usd: number;
  spend_cap_usd: number;
}

export interface SummaryResult {
  overview: string;
  files: { path: string; note: string; unsure: boolean }[];
  check_first: { path: string; reason: string }[];
}

export interface RunDetail {
  run: RunInfo;
  result: SummaryResult | null;
  comment_markdown: string | null;
  model: string | null;
  verdict_accurate: string | null;
}

export const UNSURE_NOTE = "Could not tell what this file does.";

export function countFiles(diff: string): number {
  return diff.split("\n").filter((line) => line.startsWith("diff --git ")).length;
}

async function request<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(
    url,
    body === undefined
      ? undefined
      : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
  );
  if (!res.ok) {
    // The backend sends safe, human messages in `detail` (e.g. "Couldn't read this PR...").
    let detail: unknown = null;
    try {
      detail = ((await res.json()) as { detail?: unknown }).detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : null);
  }
  return (await res.json()) as T;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string | null,
  ) {
    super(detail ?? `HTTP ${status}`);
  }
}

/** A GitHub PR link pasted on its own: the backend will fetch the diff. */
export function isPrLink(text: string): boolean {
  return /^https?:\/\/(www\.)?(github\.com|patch-diff\.githubusercontent\.com\/raw)\/[^/\s]+\/[^/\s]+\/pull\/\d+\S*$/.test(
    text.trim(),
  );
}

export function summarize(diff: string, title: string): Promise<SummarizeResult> {
  return request("/api/dev/summaries", { diff, title });
}

export function saveVerdict(summaryId: number, verdict: Verdict): Promise<{ ok: boolean }> {
  return request(`/api/dev/summaries/${summaryId}/verdict`, verdict);
}

export function listRuns(): Promise<RunList> {
  return request("/api/dev/runs");
}

export function getRun(id: number): Promise<RunDetail> {
  return request(`/api/dev/runs/${id}`);
}

export function timeAgo(iso: string, now = Date.now()): string {
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (s < 60) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} ${h === 1 ? "hour" : "hours"} ago`;
  const d = Math.round(h / 24);
  return d === 1 ? "yesterday" : `${d} days ago`;
}

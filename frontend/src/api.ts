/** All calls to our backend. Same-origin only; tokens and keys never reach the browser. */

export type RunStatus = "done" | "skipped" | "failed" | "capped" | "running";

export interface SkippedFile {
  path: string;
  reason: string;
}

export interface SummarizeResult {
  run_id: number;
  status: RunStatus;
  message: string;
  files_total: number;
  files_kept: number;
  skipped: SkippedFile[];
  summary_id: number | null;
  comment_markdown: string | null;
  /** Set only when a PR link was fetched: the diff GitHub returned (never stored). */
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
  repo?: string | null;
  pr_number?: number | null;
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
  skipped?: SkippedFile[];
}

export interface RunDetail {
  run: RunInfo;
  result: SummaryResult | null;
  comment_markdown: string | null;
  model: string | null;
  verdict_accurate: string | null;
}

export interface User {
  id: number;
  name: string;
  email: string | null;
  avatar_url: string | null;
  github_login: string | null;
}

export interface Installation {
  installation_id: number;
  account_login: string;
  account_type: string;
  repo_count: number | null;
  manage_url: string;
}

export interface Me {
  user: User | null;
  installations: Installation[];
  github_app_configured: boolean;
  github_login_configured: boolean;
}

export interface Repo {
  full_name: string;
  owner: string;
  name: string;
  private: boolean;
  installation_id: number;
  updated_at: string | null;
}

export interface PullRequest {
  number: number;
  title: string;
  author: string | null;
  updated_at: string;
  draft: boolean;
  html_url: string;
}

export const UNSURE_NOTE = "Could not tell what this file does.";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string | null,
    /** Field-level messages from the server, e.g. {email: "That email is already registered."} */
    public fields: Record<string, string> = {},
  ) {
    super(detail ?? `HTTP ${status}`);
  }
}

function csrfToken(): string {
  const m = /(?:^|;\s*)prs_csrf=([^;]+)/.exec(document.cookie);
  return m ? decodeURIComponent(m[1]) : "";
}

async function request<T>(url: string, init?: { method?: string; body?: unknown }): Promise<T> {
  const method = init?.method ?? (init?.body === undefined ? "GET" : "POST");
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") {
    headers["Content-Type"] = "application/json";
    headers["X-CSRF-Token"] = csrfToken();
  }
  const res = await fetch(url, {
    method,
    headers,
    credentials: "same-origin",
    body: init?.body === undefined ? undefined : JSON.stringify(init.body),
  });
  if (!res.ok) {
    // The backend sends human messages in `detail` (string) and optional `fields`.
    let detail: string | null = null;
    let fields: Record<string, string> = {};
    try {
      const data = (await res.json()) as { detail?: unknown; fields?: unknown };
      if (typeof data.detail === "string") detail = data.detail;
      if (data.fields && typeof data.fields === "object") fields = data.fields as Record<string, string>;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, detail, fields);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function countFiles(diff: string): number {
  return diff.split("\n").filter((line) => line.startsWith("diff --git ")).length;
}

/** A GitHub PR link pasted on its own: the backend will fetch the diff. */
export function isPrLink(text: string): boolean {
  return /^https?:\/\/(www\.)?(github\.com|patch-diff\.githubusercontent\.com\/raw)\/[^/\s]+\/[^/\s]+\/pull\/\d+\S*$/.test(
    text.trim(),
  );
}

// ---- summaries & runs
export const summarize = (diff: string, title: string) =>
  request<SummarizeResult>("/api/summaries", { body: { diff, title } });
export const saveVerdict = (summaryId: number, verdict: Verdict) =>
  request<{ ok: boolean }>(`/api/summaries/${summaryId}/verdict`, { body: verdict });
export const listRuns = () => request<RunList>("/api/runs");
export const getRun = (id: number) => request<RunDetail>(`/api/runs/${id}`);

// ---- auth
export const getMe = () => request<Me>("/api/auth/me");
export const signup = (name: string, email: string, password: string) =>
  request<{ user: User }>("/api/auth/signup", { body: { name, email, password } });
export const login = (email: string, password: string) =>
  request<{ user: User }>("/api/auth/login", { body: { email, password } });
export const logout = () => request<void>("/api/auth/logout", { body: {} });

// ---- GitHub App
export const listRepos = () => request<{ repos: Repo[] }>("/api/github/repos");
export const listPulls = (owner: string, repo: string) =>
  request<{ pulls: PullRequest[] }>(`/api/github/repos/${owner}/${repo}/pulls`);
export const summarizePull = (owner: string, repo: string, number: number) =>
  request<SummarizeResult>(`/api/github/repos/${owner}/${repo}/pulls/${number}/summarize`, { body: {} });

// ---- formatting
export function timeAgo(iso: string, now = Date.now()): string {
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (s < 60) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} ${h === 1 ? "hour" : "hours"} ago`;
  const d = Math.round(h / 24);
  if (d === 1) return "yesterday";
  if (d < 30) return `${d} days ago`;
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

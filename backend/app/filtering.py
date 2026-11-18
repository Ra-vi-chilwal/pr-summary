"""Decide which files are worth summarizing, and whether to skip the whole PR."""

from dataclasses import dataclass, field
from pathlib import PurePosixPath

from app.diff import FileDiff

MAX_FILES = 100
MAX_PATCH_CHARS = 300_000  # ~75k tokens; keeps one run well under the monthly cap

LOCKFILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "npm-shrinkwrap.json",
    "poetry.lock", "pipfile.lock", "uv.lock", "cargo.lock", "composer.lock", "gemfile.lock",
    "go.sum", "pubspec.lock", "podfile.lock", "packages.lock.json", "flake.lock",
}  # fmt: skip
GENERATED_DIRS = {"dist", "node_modules", "vendor", ".next", "coverage", "__generated__"}
GENERATED_SUFFIXES = (".min.js", ".min.css", ".map", ".snap", "_pb2.py", ".pb.go")
BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg", ".bmp", ".pdf", ".zip",
    ".gz", ".tar", ".woff", ".woff2", ".ttf", ".eot", ".otf", ".mp4", ".mp3", ".mov",
    ".exe", ".dll", ".so", ".dylib", ".jar",
}  # fmt: skip


@dataclass
class SkippedFile:
    path: str
    reason: str  # lockfile | generated | image or binary


@dataclass
class Plan:
    """skip_kind is None when the PR should be summarized."""

    files_total: int
    kept: list[FileDiff] = field(default_factory=list)
    skipped: list[SkippedFile] = field(default_factory=list)
    skip_kind: str | None = None
    message: str = ""


def skip_reason(f: FileDiff) -> str | None:
    p = PurePosixPath(f.path)
    name = p.name.lower()
    if name in LOCKFILES:
        return "lockfile"
    if f.is_binary or p.suffix.lower() in BINARY_EXTENSIONS:
        return "image or binary"
    if any(part in GENERATED_DIRS for part in p.parts[:-1]):
        return "generated"
    if name.endswith(GENERATED_SUFFIXES) or ".generated." in name:
        return "generated"
    return None


def plan_files(files: list[FileDiff]) -> Plan:
    plan = Plan(files_total=len(files))
    if not files:
        plan.skip_kind = "empty"
        plan.message = "Nothing to summarize. We couldn't find any changed files in this diff."
        return plan
    if len(files) > MAX_FILES:
        plan.skip_kind = "too_many_files"
        plan.message = (
            f"This PR changes {len(files)} files. We skip PRs with more than {MAX_FILES} files."
        )
        return plan

    for f in files:
        reason = skip_reason(f)
        if reason:
            plan.skipped.append(SkippedFile(f.path, reason))
        else:
            plan.kept.append(f)

    if not plan.kept:
        plan.skip_kind = "nothing_to_summarize"
        plan.message = "Nothing to summarize. Only lockfiles, generated files or images changed."
    elif sum(len(f.patch) for f in plan.kept) > MAX_PATCH_CHARS:
        plan.skip_kind = "too_big"
        plan.message = "This PR's diff is too big to summarize well, so we skipped it."
    return plan

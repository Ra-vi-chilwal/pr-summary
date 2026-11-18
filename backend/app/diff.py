"""Parse a unified git diff (as from `gh pr diff` or a PR's .diff URL) into files."""

import re
from dataclasses import dataclass

_HEADER = re.compile(r"^diff --git a/(.+) b/(.+)$")


@dataclass
class FileDiff:
    path: str
    old_path: str | None = None
    status: str = "modified"  # added | modified | deleted | renamed
    additions: int = 0
    deletions: int = 0
    is_binary: bool = False
    patch: str = ""


def _strip_prefix(p: str, prefix: str) -> str:
    return p[len(prefix) :] if p.startswith(prefix) else p


def parse_diff(text: str) -> list[FileDiff]:
    files: list[FileDiff] = []
    current: FileDiff | None = None
    lines: list[str] = []
    in_hunk = False

    def finish() -> None:
        if current is not None:
            current.patch = "\n".join(lines)
            files.append(current)

    for line in text.splitlines():
        header = _HEADER.match(line)
        if header:
            finish()
            current = FileDiff(path=header.group(2), old_path=header.group(1))
            lines = [line]
            in_hunk = False
            continue
        if current is None:
            continue
        lines.append(line)

        if line.startswith("@@"):
            in_hunk = True
        elif in_hunk:
            if line.startswith("+"):
                current.additions += 1
            elif line.startswith("-"):
                current.deletions += 1
        elif line.startswith("new file mode"):
            current.status = "added"
        elif line.startswith("deleted file mode"):
            current.status = "deleted"
        elif line.startswith("rename from "):
            current.old_path = line[len("rename from ") :]
            current.status = "renamed"
        elif line.startswith("rename to "):
            current.path = line[len("rename to ") :]
        elif line.startswith("Binary files ") or line == "GIT binary patch":
            current.is_binary = True
        elif line.startswith("+++ "):
            target = line[4:].strip()
            if target != "/dev/null":
                current.path = _strip_prefix(target, "b/")

    finish()
    return files

"""Shape of the AI's answer, plus checks that keep it honest about the real diff."""

from pydantic import BaseModel

UNSURE_NOTE = "Could not tell what this file does."
MAX_CHECK_FIRST = 3


class FileNote(BaseModel):
    path: str
    note: str
    unsure: bool


class CheckFirst(BaseModel):
    path: str
    reason: str


class SummaryResult(BaseModel):
    overview: str
    files: list[FileNote]
    check_first: list[CheckFirst]


# JSON schema sent to Claude as a structured output format.
SUMMARY_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "overview": {"type": "string"},
        "files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "note": {"type": "string"},
                    "unsure": {"type": "boolean"},
                },
                "required": ["path", "note", "unsure"],
                "additionalProperties": False,
            },
        },
        "check_first": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["path", "reason"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["overview", "files", "check_first"],
    "additionalProperties": False,
}


def reconcile(result: SummaryResult, kept_paths: list[str]) -> SummaryResult:
    """Match the AI's answer to the files that were really sent.

    - Drops notes and check-first entries for paths that aren't in the diff.
    - Adds an "unsure" note for any file the AI left out, so nothing looks silently fine.
    - Keeps at most 3 check-first files.
    """
    kept = set(kept_paths)
    by_path: dict[str, FileNote] = {}
    for n in result.files:
        if n.path in kept and n.path not in by_path:
            note = n.note.strip()
            by_path[n.path] = FileNote(path=n.path, note=note, unsure=n.unsure or not note)

    files = [by_path.get(p) or FileNote(path=p, note="", unsure=True) for p in kept_paths]

    check_first: list[CheckFirst] = []
    seen: set[str] = set()
    for c in result.check_first:
        if c.path in kept and c.path not in seen and len(check_first) < MAX_CHECK_FIRST:
            seen.add(c.path)
            check_first.append(CheckFirst(path=c.path, reason=c.reason.strip()))

    return SummaryResult(overview=result.overview.strip(), files=files, check_first=check_first)

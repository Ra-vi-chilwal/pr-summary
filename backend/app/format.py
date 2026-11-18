"""Turn a summary into the plain GitHub markdown comment we would post."""

from app.filtering import SkippedFile
from app.schema import UNSURE_NOTE, SummaryResult

COMMENT_MARKER = "<!-- pr-summary-bot -->"  # lets us find and edit our one comment later
AI_FOOTER = "Written by AI. It can be wrong."


def _file_line(path: str, note: str, unsure: bool) -> str:
    if unsure:
        text = UNSURE_NOTE if not note or note == UNSURE_NOTE else f"{UNSURE_NOTE} {note}"
    else:
        text = note
    return f"- `{path}`: {text}"


def format_comment(result: SummaryResult, skipped: list[SkippedFile]) -> str:
    lines = [COMMENT_MARKER, "## PR summary", "", result.overview, "", "### Check these first"]
    if result.check_first:
        for i, c in enumerate(result.check_first, start=1):
            lines.append(f"{i}. `{c.path}`: {c.reason}")
    else:
        lines.append("Could not pick the riskiest files. Read the diff as usual.")

    lines += ["", "### What changed, file by file"]
    lines += [_file_line(f.path, f.note, f.unsure) for f in result.files]

    if skipped:
        lines += [
            "",
            f"Skipped {len(skipped)} file(s): "
            + ", ".join(f"`{s.path}` ({s.reason})" for s in skipped),
        ]

    lines += ["", "---", AI_FOOTER]
    return "\n".join(lines)

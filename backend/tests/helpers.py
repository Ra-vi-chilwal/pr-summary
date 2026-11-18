from app.ai import AIError, AIResponse, TokenUsage
from app.schema import CheckFirst, FileNote, SummaryResult


def file_diff(path: str, added: list[str] | None = None, removed: list[str] | None = None,
              new: bool = False) -> str:  # fmt: skip
    added = added if added is not None else ["print('hi')"]
    removed = removed or []
    header = [f"diff --git a/{path} b/{path}"]
    if new:
        header += ["new file mode 100644", "index 0000000..1111111", "--- /dev/null"]
    else:
        header += ["index 1111111..2222222 100644", f"--- a/{path}"]
    header.append(f"+++ b/{path}")
    body = [f"@@ -1,{len(removed)} +1,{len(added)} @@"]
    body += [f"-{line}" for line in removed] + [f"+{line}" for line in added]
    return "\n".join(header + body)


def make_diff(*paths: str) -> str:
    return "\n".join(file_diff(p) for p in paths) + "\n"


class FakeSummarizer:
    """Stands in for Claude. `script` is a list of AIResponse or exceptions, used in order."""

    def __init__(self, script: list | None = None):
        self.script = list(script or [])
        self.calls: list[tuple[str, str]] = []

    def summarize(self, system: str, user: str) -> AIResponse:
        self.calls.append((system, user))
        item = self.script.pop(0) if self.script else None
        if isinstance(item, Exception):
            raise item
        return item or ok_response(["src/app.py"])


def ok_response(paths: list[str], input_tokens: int = 1000, output_tokens: int = 200,
                model: str = "claude-opus-5-5") -> AIResponse:  # fmt: skip
    return AIResponse(
        result=SummaryResult(
            overview="Adds a greeting.",
            files=[FileNote(path=p, note=f"Changes {p}.", unsure=False) for p in paths],
            check_first=[CheckFirst(path=paths[0], reason="New logic with no tests.")],
        ),
        usage=TokenUsage(model=model, input_tokens=input_tokens, output_tokens=output_tokens),
    )


def retryable_error() -> AIError:
    return AIError("http_529", retryable=True)

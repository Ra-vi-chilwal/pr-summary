"""One summary run: parse -> filter -> spend check -> one AI call (+1 retry) -> format -> save.

The diff is held in memory only. We save the run, the summary and token usage.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import AIError, AIResponse, Summarizer, TokenUsage, cost_microusd
from app.diff import parse_diff
from app.filtering import SkippedFile, plan_files
from app.format import format_comment
from app.models import Run, Summary, Usage, utcnow
from app.prompt import SYSTEM_PROMPT, build_user_message
from app.schema import reconcile

log = logging.getLogger("pr_summary")

FAILED_MESSAGE = "Failed, nothing posted."
DONE_MESSAGE = "Summary ready. Nothing was posted to GitHub (dev mode)."
MAX_ATTEMPTS = 2  # one call + one retry


@dataclass
class Outcome:
    run_id: int
    status: str  # done | skipped | failed | capped
    message: str
    files_total: int = 0
    files_kept: int = 0
    skipped: list[SkippedFile] = field(default_factory=list)
    summary_id: int | None = None
    comment_markdown: str | None = None


def month_spend_microusd(session: Session, now: datetime | None = None) -> int:
    now = now or utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = session.scalar(
        select(func.coalesce(func.sum(Usage.cost_microusd), 0)).where(
            Usage.created_at >= month_start
        )
    )
    return int(total or 0)


def _record_usage(session: Session, run: Run, usage: TokenUsage) -> None:
    session.add(
        Usage(
            run_id=run.id,
            model=usage.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_microusd=cost_microusd(usage.model, usage.input_tokens, usage.output_tokens),
        )
    )


def _finish(session: Session, run: Run, status: str, message: str, error_kind: str | None = None):
    run.status = status
    run.message = message
    run.error_kind = error_kind
    run.finished_at = datetime.now(UTC).replace(tzinfo=None)
    session.commit()


def summarize_diff(
    session: Session,
    summarizer: Summarizer | None,
    diff_text: str,
    title: str = "",
    spend_cap_usd: float = 10.0,
) -> Outcome:
    run = Run(source="dev_paste", status="running", title=title[:300])
    session.add(run)
    session.flush()

    plan = plan_files(parse_diff(diff_text))
    run.files_total = plan.files_total
    run.files_kept = len(plan.kept)
    outcome = Outcome(
        run_id=run.id,
        status="skipped",
        message=plan.message,
        files_total=plan.files_total,
        files_kept=len(plan.kept),
        skipped=plan.skipped,
    )

    if plan.skip_kind:
        _finish(session, run, "skipped", plan.message, plan.skip_kind)
        return outcome

    if month_spend_microusd(session) >= int(spend_cap_usd * 1_000_000):
        outcome.status = "capped"
        outcome.message = (
            f"Monthly AI spend limit (${spend_cap_usd:.0f}) reached. Nothing was sent to the AI."
        )
        _finish(session, run, "capped", outcome.message, "spend_cap")
        return outcome

    outcome.status = "failed"
    outcome.message = FAILED_MESSAGE
    if summarizer is None:
        log.warning("run %s failed: no_api_key", run.id)
        _finish(session, run, "failed", FAILED_MESSAGE, "no_api_key")
        return outcome

    user_message = build_user_message(plan.kept, title)
    response: AIResponse | None = None
    error_kind = "unknown"
    for _ in range(MAX_ATTEMPTS):
        run.ai_calls += 1
        try:
            response = summarizer.summarize(SYSTEM_PROMPT, user_message)
            _record_usage(session, run, response.usage)
            break
        except AIError as e:
            error_kind = e.kind
            if e.usage:
                _record_usage(session, run, e.usage)
            if not e.retryable:
                break
        except Exception as e:  # never let an unexpected error post anything
            error_kind = type(e).__name__
            break

    if response is None:
        log.warning("run %s failed after %s AI call(s): %s", run.id, run.ai_calls, error_kind)
        _finish(session, run, "failed", FAILED_MESSAGE, error_kind)
        return outcome

    result = reconcile(response.result, [f.path for f in plan.kept])
    comment = format_comment(result, plan.skipped)
    summary = Summary(
        run_id=run.id,
        model=response.usage.model,
        comment_markdown=comment,
        result_json={
            **result.model_dump(),
            "skipped": [{"path": s.path, "reason": s.reason} for s in plan.skipped],
        },
    )
    session.add(summary)
    session.flush()
    _finish(session, run, "done", DONE_MESSAGE)

    outcome.status = "done"
    outcome.message = DONE_MESSAGE
    outcome.summary_id = summary.id
    outcome.comment_markdown = comment
    return outcome

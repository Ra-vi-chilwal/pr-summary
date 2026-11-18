"""Webhook-driven summaries: one AI call per new head commit, one comment per PR (edited later).

Rules from AGENTS.md: max 1 AI call per push (plus one retry), skip >100 files or
lockfile-only PRs, 50 reviews per repo per month, and if anything fails post nothing.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app import audit
from app.ai import Summarizer
from app.config import Settings
from app.format import COMMENT_MARKER
from app.github_app import GitHub, GitHubError
from app.logging_setup import get_logger
from app.models import GitHubInstallation, PRComment, Repo, Run, utcnow
from app.service import FAILED_MESSAGE, summarize_diff

log = get_logger("pr_summary.bot")


@dataclass
class PREvent:
    installation_id: int
    repo_github_id: int
    owner: str
    repo: str
    number: int
    head_sha: str
    title: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"


def upsert_repo(db: Session, github_id: int | None, full_name: str) -> Repo:
    repo = None
    if github_id:
        repo = db.scalar(select(Repo).where(Repo.github_id == github_id))
    if repo is None:
        repo = db.scalar(select(Repo).where(Repo.full_name == full_name))
    if repo is None:
        repo = Repo(github_id=github_id, full_name=full_name)
        db.add(repo)
    repo.full_name = full_name
    if github_id and not repo.github_id:
        repo.github_id = github_id
    db.flush()
    return repo


def reviews_this_month(db: Session, repo_id: int) -> int:
    month_start = utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return int(
        db.scalar(
            select(func.count(Run.id)).where(
                Run.repo_id == repo_id, Run.created_at >= month_start, Run.ai_calls > 0
            )
        )
        or 0
    )


def handle_pull_request(
    session_factory: sessionmaker,
    github: GitHub,
    summarizer: Summarizer | None,
    settings: Settings,
    ev: PREvent,
) -> str:
    """Returns what happened (for logs and tests).

    One of: skipped_duplicate, capped, failed, skipped, posted, updated.
    """
    with session_factory() as db:
        repo = upsert_repo(db, ev.repo_github_id, ev.full_name)
        inst = db.scalar(
            select(GitHubInstallation).where(
                GitHubInstallation.installation_id == ev.installation_id
            )
        )
        user_id = inst.user_id if inst else None
        ctx = {"repo": ev.full_name, "pr": ev.number, "sha": ev.head_sha[:12]}

        dup = db.scalar(
            select(Run.id).where(
                Run.repo_id == repo.id,
                Run.pr_number == ev.number,
                Run.commit_sha == ev.head_sha,
                Run.status.in_(("done", "running", "skipped")),
            )
        )
        if dup:
            log.info("pr_event_skipped", reason="same_commit", **ctx)
            db.commit()
            return "skipped_duplicate"

        if reviews_this_month(db, repo.id) >= settings.reviews_per_repo_per_month:
            db.add(
                Run(
                    source="webhook", status="capped", title=ev.title[:300], repo_id=repo.id,
                    pr_number=ev.number, commit_sha=ev.head_sha, user_id=user_id,
                    message=f"This repository used its {settings.reviews_per_repo_per_month} "
                    "summaries for the month. Nothing was posted.",
                    error_kind="repo_cap", files_total=0, files_kept=0, ai_calls=0,
                )
            )  # fmt: skip
            db.commit()
            log.warning("pr_event_skipped", reason="repo_monthly_cap", **ctx)
            return "capped"

        try:
            diff = github.get_pull_diff(ev.installation_id, ev.owner, ev.repo, ev.number)
        except GitHubError as e:
            db.add(
                Run(
                    source="webhook", status="failed", title=ev.title[:300], repo_id=repo.id,
                    pr_number=ev.number, commit_sha=ev.head_sha, user_id=user_id,
                    message=f"{FAILED_MESSAGE} {e.message}", error_kind=e.kind,
                    files_total=0, files_kept=0, ai_calls=0,
                )
            )  # fmt: skip
            db.commit()
            log.warning("pr_event_failed", stage="diff", kind=e.kind, **ctx)
            return "failed"

        outcome = summarize_diff(
            db, summarizer, diff, ev.title, settings.monthly_spend_cap_usd,
            user_id=user_id, repo_id=repo.id, pr_number=ev.number,
            commit_sha=ev.head_sha, source="webhook",
        )  # fmt: skip
        del diff
        if outcome.status != "done" or not outcome.comment_markdown:
            log.info("pr_event_not_posted", status=outcome.status, **ctx)
            return outcome.status

        try:
            action = post_or_update(db, github, ev, outcome.comment_markdown)
        except GitHubError as e:
            run = db.get(Run, outcome.run_id)
            run.status, run.message, run.error_kind = (
                "failed",
                f"{FAILED_MESSAGE} {e.message}",
                e.kind,
            )
            db.commit()
            audit.record(db, "summary_post_failed", user_id=user_id, kind=e.kind, **ctx)
            return "failed"

        run = db.get(Run, outcome.run_id)
        run.message = (
            "Summary posted on GitHub." if action == "posted" else "Summary updated on GitHub."
        )
        db.commit()
        audit.record(db, "summary_posted", user_id=user_id, action=action, run_id=run.id, **ctx)
        return action


def post_or_update(db: Session, github: GitHub, ev: PREvent, body: str) -> str:
    """Edit our existing comment if there is one; otherwise create it. Returns posted|updated."""
    row = db.scalar(
        select(PRComment).where(
            PRComment.repo_full_name == ev.full_name, PRComment.pr_number == ev.number
        )
    )
    comment_id = row.comment_id if row else None
    if comment_id is None:
        comment_id = github.find_bot_comment(
            ev.installation_id, ev.owner, ev.repo, ev.number, COMMENT_MARKER
        )
    if comment_id is not None:
        try:
            github.update_comment(ev.installation_id, ev.owner, ev.repo, comment_id, body)
            _save(db, row, ev, comment_id)
            return "updated"
        except GitHubError as e:
            if e.kind != "no_access":  # 404: someone deleted our comment; post a fresh one
                raise
    comment_id = github.create_comment(ev.installation_id, ev.owner, ev.repo, ev.number, body)
    _save(db, row, ev, comment_id)
    return "posted"


def _save(db: Session, row: PRComment | None, ev: PREvent, comment_id: int) -> None:
    if row is None:
        row = PRComment(repo_full_name=ev.full_name, pr_number=ev.number, comment_id=comment_id,
                        installation_id=ev.installation_id)  # fmt: skip
        db.add(row)
    row.comment_id = comment_id
    row.installation_id = ev.installation_id
    row.updated_at = utcnow()
    db.commit()

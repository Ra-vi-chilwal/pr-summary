"""Summaries: Try a diff (public), the user's runs, and verdicts."""

from collections.abc import Callable
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.github_public import PRFetchError, PRLink, parse_pr_link
from app.models import Repo, Run, Summary, User, utcnow
from app.ratelimit import limit
from app.security import ANON_RUNS_COOKIE, current_user, optional_user, sign, unsign
from app.service import Outcome, month_spend_microusd, summarize_diff


class SummarizeIn(BaseModel):
    diff: str = Field(max_length=2_000_000)
    title: str = Field(default="", max_length=300)


class SkippedOut(BaseModel):
    path: str
    reason: str


class SummarizeOut(BaseModel):
    run_id: int
    status: str
    message: str
    files_total: int
    files_kept: int
    skipped: list[SkippedOut]
    summary_id: int | None
    comment_markdown: str | None
    # Only set when we fetched the diff ourselves: it goes back to the user's own browser
    # so the summary page can show it. It is never stored.
    diff: str | None = None
    title: str = ""


class VerdictIn(BaseModel):
    accurate: Literal["yes", "partly", "no"]
    saved_time: bool | None = None
    note: str = Field(default="", max_length=5000)


class RunOut(BaseModel):
    id: int
    title: str
    status: str
    message: str
    files_total: int
    files_kept: int
    created_at: str
    summary_id: int | None
    repo: str | None = None
    pr_number: int | None = None


class RunListOut(BaseModel):
    runs: list[RunOut]
    runs_this_month: int
    spend_this_month_usd: float
    spend_cap_usd: float


class RunDetailOut(BaseModel):
    run: RunOut
    result: dict | None
    comment_markdown: str | None
    model: str | None
    verdict_accurate: str | None


def run_out(run: Run, summary_id: int | None, repo: str | None = None) -> RunOut:
    return RunOut(
        id=run.id,
        title=run.title,
        status=run.status,
        message=run.message,
        files_total=run.files_total,
        files_kept=run.files_kept,
        created_at=run.created_at.isoformat() + "Z",
        summary_id=summary_id,
        repo=repo,
        pr_number=run.pr_number,
    )


def outcome_out(outcome: Outcome, diff: str | None = None, title: str = "") -> SummarizeOut:
    return SummarizeOut(
        diff=diff,
        title=title,
        run_id=outcome.run_id,
        status=outcome.status,
        message=outcome.message,
        files_total=outcome.files_total,
        files_kept=outcome.files_kept,
        skipped=[SkippedOut(path=s.path, reason=s.reason) for s in outcome.skipped],
        summary_id=outcome.summary_id,
        comment_markdown=outcome.comment_markdown,
    )


PRFetcher = Callable[[PRLink, User | None, Session], tuple[str, str]]


def build_router(pr_fetcher: PRFetcher) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["summaries"])

    @router.post("/summaries", response_model=SummarizeOut)
    def create_summary(
        body: SummarizeIn,
        request: Request,
        response: Response,
        session: Session = Depends(get_session),
        user: User | None = Depends(optional_user),
    ) -> SummarizeOut:
        settings = request.app.state.settings
        if user is None:  # Try a diff is public; keep anonymous AI use bounded.
            limit(request, "anon_summary", settings.anon_summary_rate_limit, window_s=3600)
        diff_text, title, fetched = body.diff, body.title, False
        link = parse_pr_link(body.diff)
        if link:
            try:
                diff_text, pr_title = pr_fetcher(link, user, session)
            except PRFetchError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e
            title = title.strip() or pr_title or f"{link.repo} #{link.number}"
            fetched = True
        outcome = summarize_diff(
            session,
            request.app.state.summarizer,
            diff_text,
            title,
            settings.monthly_spend_cap_usd,
            user_id=user.id if user else None,
        )
        if user is None:
            remember_anon_run(request, response, outcome.run_id)
        return outcome_out(outcome, diff_text if fetched else None, title)

    @router.post("/summaries/{summary_id}/verdict")
    def save_verdict(
        summary_id: int,
        body: VerdictIn,
        session: Session = Depends(get_session),
        user: User | None = Depends(optional_user),
    ) -> dict:
        summary = session.get(Summary, summary_id)
        run = session.get(Run, summary.run_id) if summary else None
        if summary is None or run is None or (run.user_id and (not user or run.user_id != user.id)):
            raise HTTPException(status_code=404, detail="Summary not found.")
        summary.verdict_accurate = body.accurate
        summary.verdict_saved_time = body.saved_time
        summary.verdict_note = body.note.strip() or None
        summary.verdict_at = utcnow()
        session.commit()
        return {"ok": True}

    @router.get("/runs", response_model=RunListOut)
    def list_runs(
        request: Request,
        session: Session = Depends(get_session),
        user: User = Depends(current_user),
    ) -> RunListOut:
        rows = session.execute(
            select(Run, Summary.id, Repo.full_name)
            .outerjoin(Summary, Summary.run_id == Run.id)
            .outerjoin(Repo, Repo.id == Run.repo_id)
            .where(Run.user_id == user.id)
            .order_by(Run.id.desc())
            .limit(100)
        ).all()
        month_start = utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return RunListOut(
            runs=[run_out(run, sid, repo) for run, sid, repo in rows],
            runs_this_month=sum(1 for run, _, _ in rows if run.created_at >= month_start),
            spend_this_month_usd=round(month_spend_microusd(session) / 1_000_000, 4),
            spend_cap_usd=request.app.state.settings.monthly_spend_cap_usd,
        )

    @router.get("/runs/{run_id}", response_model=RunDetailOut)
    def get_run(
        run_id: int,
        request: Request,
        session: Session = Depends(get_session),
        user: User = Depends(current_user),
    ) -> RunDetailOut:
        run = session.get(Run, run_id)
        # Your own runs, plus anonymous runs made in this same browser before signing in.
        claimable = run is not None and run.user_id is None and run.id in anon_runs(request)
        if run is None or (run.user_id != user.id and not claimable):
            raise HTTPException(status_code=404, detail="Summary not found.")
        if claimable:
            run.user_id = user.id  # now it shows on your dashboard
            session.commit()
        summary = session.scalar(select(Summary).where(Summary.run_id == run.id))
        repo = session.get(Repo, run.repo_id).full_name if run.repo_id else None
        return RunDetailOut(
            run=run_out(run, summary.id if summary else None, repo),
            result=summary.result_json if summary else None,
            comment_markdown=summary.comment_markdown if summary else None,
            model=summary.model if summary else None,
            verdict_accurate=summary.verdict_accurate if summary else None,
        )

    return router


def anon_runs(request: Request) -> list[int]:
    data = unsign(request.app.state.settings.secret_key, request.cookies.get(ANON_RUNS_COOKIE))
    ids = (data or {}).get("runs", [])
    return [i for i in ids if isinstance(i, int)]


def remember_anon_run(request: Request, response: Response, run_id: int) -> None:
    """Signed list of runs this browser made while signed out; only it can claim them."""
    settings = request.app.state.settings
    ids = (anon_runs(request) + [run_id])[-20:]
    response.set_cookie(
        ANON_RUNS_COOKIE,
        sign(settings.secret_key, {"runs": ids}),
        max_age=7 * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api",
    )

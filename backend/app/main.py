import logging
from collections.abc import Callable
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import Summarizer, make_summarizer
from app.config import Settings
from app.db import Base, get_session, make_engine, make_session_factory
from app.github_public import PRFetchError, PRLink, fetch_public_pr, parse_pr_link
from app.models import Run, Summary, utcnow
from app.service import month_spend_microusd, summarize_diff

logging.basicConfig(level=logging.INFO)


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
    # Only set when the user pasted a PR link: the fetched diff goes back to their own
    # browser so the Review screen can show it. It is never stored.
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


def _run_out(run: Run, summary_id: int | None) -> RunOut:
    return RunOut(
        id=run.id,
        title=run.title,
        status=run.status,
        message=run.message,
        files_total=run.files_total,
        files_kept=run.files_kept,
        created_at=run.created_at.isoformat() + "Z",
        summary_id=summary_id,
    )


_UNSET = object()


def create_app(
    settings: Settings | None = None,
    summarizer: object = _UNSET,
    pr_fetcher: Callable[[PRLink], tuple[str, str]] = fetch_public_pr,
) -> FastAPI:
    settings = settings or Settings()
    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)

    if summarizer is _UNSET:
        summarizer = make_summarizer(
            settings.ai_provider,
            settings.anthropic_api_key,
            settings.gemini_api_key,
            settings.gemini_model,
        )

    app = FastAPI(title="PR summary")
    app.state.session_factory = make_session_factory(engine)
    app.state.summarizer = summarizer
    app.state.settings = settings

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    if settings.enable_dev_tools:

        @app.post("/api/dev/summaries", response_model=SummarizeOut)
        def create_summary(body: SummarizeIn, session: Session = Depends(get_session)):
            ai: Summarizer | None = app.state.summarizer
            diff_text, title, fetched = body.diff, body.title, False
            link = parse_pr_link(body.diff)
            if link:
                try:
                    diff_text, pr_title = pr_fetcher(link)
                except PRFetchError as e:
                    raise HTTPException(status_code=422, detail=str(e)) from e
                title = title.strip() or pr_title or f"{link.repo} #{link.number}"
                fetched = True
            outcome = summarize_diff(session, ai, diff_text, title, settings.monthly_spend_cap_usd)
            return SummarizeOut(
                diff=diff_text if fetched else None,
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

        @app.post("/api/dev/summaries/{summary_id}/verdict")
        def save_verdict(
            summary_id: int, body: VerdictIn, session: Session = Depends(get_session)
        ) -> dict:
            summary = session.get(Summary, summary_id)
            if summary is None:
                raise HTTPException(status_code=404, detail="Summary not found.")
            summary.verdict_accurate = body.accurate
            summary.verdict_saved_time = body.saved_time
            summary.verdict_note = body.note.strip() or None
            summary.verdict_at = utcnow()
            session.commit()
            return {"ok": True}

        @app.get("/api/dev/runs", response_model=RunListOut)
        def list_runs(session: Session = Depends(get_session)) -> RunListOut:
            rows = session.execute(
                select(Run, Summary.id)
                .outerjoin(Summary, Summary.run_id == Run.id)
                .order_by(Run.id.desc())
                .limit(100)
            ).all()
            month_start = utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return RunListOut(
                runs=[_run_out(run, summary_id) for run, summary_id in rows],
                runs_this_month=sum(1 for run, _ in rows if run.created_at >= month_start),
                spend_this_month_usd=round(month_spend_microusd(session) / 1_000_000, 4),
                spend_cap_usd=settings.monthly_spend_cap_usd,
            )

        @app.get("/api/dev/runs/{run_id}", response_model=RunDetailOut)
        def get_run(run_id: int, session: Session = Depends(get_session)) -> RunDetailOut:
            run = session.get(Run, run_id)
            if run is None:
                raise HTTPException(status_code=404, detail="Run not found.")
            summary = session.scalar(select(Summary).where(Summary.run_id == run.id))
            return RunDetailOut(
                run=_run_out(run, summary.id if summary else None),
                result=summary.result_json if summary else None,
                comment_markdown=summary.comment_markdown if summary else None,
                model=summary.model if summary else None,
                verdict_accurate=summary.verdict_accurate if summary else None,
            )

    return app


# Run with: uvicorn app.main:create_app --factory

"""Tables: repos, runs, summaries, usage. We never store the diff."""

from datetime import UTC, datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Repo(Base):
    __tablename__ = "repos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    github_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    full_name: Mapped[str] = mapped_column(String(300))
    installed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo_id: Mapped[int | None] = mapped_column(ForeignKey("repos.id"))
    pr_number: Mapped[int | None] = mapped_column(Integer)
    commit_sha: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(300), default="")
    source: Mapped[str] = mapped_column(String(20))  # "dev_paste" now, "webhook" later
    # running | done | skipped | failed | capped
    status: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text, default="")
    error_kind: Mapped[str | None] = mapped_column(String(40))
    files_total: Mapped[int] = mapped_column(Integer, default=0)
    files_kept: Mapped[int] = mapped_column(Integer, default=0)
    ai_calls: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), unique=True)
    model: Mapped[str] = mapped_column(String(64))
    comment_markdown: Mapped[str] = mapped_column(Text)
    result_json: Mapped[dict] = mapped_column(JSON)
    # Reviewer verdict for Milestone 1 (tests the riskiest assumption).
    verdict_accurate: Mapped[str | None] = mapped_column(String(10))  # yes | partly | no
    verdict_saved_time: Mapped[bool | None] = mapped_column(Boolean)
    verdict_note: Mapped[str | None] = mapped_column(Text)
    verdict_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Usage(Base):
    __tablename__ = "usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    model: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    cost_microusd: Mapped[int] = mapped_column(Integer)  # 1_000_000 = $1
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

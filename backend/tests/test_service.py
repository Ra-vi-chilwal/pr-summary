import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.ai import AIError, TokenUsage
from app.db import Base, make_engine, make_session_factory
from app.models import Run, Summary, Usage
from app.service import FAILED_MESSAGE, month_spend_microusd, summarize_diff
from tests.helpers import FakeSummarizer, make_diff, ok_response, retryable_error

SECRET_CODE = "TOP_SECRET_FUNCTION_BODY_42"


@pytest.fixture
def session():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = make_session_factory(engine)()
    yield s
    s.close()


def all_stored_text(session: Session) -> str:
    """Every value in every table, as one string."""
    chunks = []
    for table in inspect(session.bind).get_table_names():
        for row in session.execute(text(f"SELECT * FROM {table}")):  # noqa: S608
            chunks.append(repr(tuple(row)))
    return "\n".join(chunks)


def test_success_makes_one_call_and_stores_summary_not_diff(session):
    diff = make_diff("src/app.py", "package-lock.json").replace("print('hi')", SECRET_CODE)
    ai = FakeSummarizer([ok_response(["src/app.py"])])

    out = summarize_diff(session, ai, diff, title="Add greeting")

    assert out.status == "done"
    assert len(ai.calls) == 1
    assert SECRET_CODE in ai.calls[0][1]  # the code is sent to the AI...
    assert SECRET_CODE not in all_stored_text(session)  # ...but never stored
    assert "package-lock.json" not in ai.calls[0][1].split("<files>")[1]
    assert out.comment_markdown.endswith("Written by AI. It can be wrong.")
    summary = session.get(Summary, out.summary_id)
    assert summary.model == "claude-opus-5-5"
    run = session.get(Run, out.run_id)
    assert (run.status, run.files_total, run.files_kept, run.ai_calls) == ("done", 2, 1, 1)
    usage = session.scalars(select(Usage)).one()
    assert usage.cost_microusd == 1000 * 4 + 200 * 20


def test_ai_down_retries_once_then_fails_and_posts_nothing(session):
    ai = FakeSummarizer([retryable_error(), retryable_error(), ok_response(["src/app.py"])])

    out = summarize_diff(session, ai, make_diff("src/app.py"))

    assert out.status == "failed"
    assert out.message == FAILED_MESSAGE == "Failed, nothing posted."
    assert len(ai.calls) == 2
    assert out.comment_markdown is None
    assert session.scalars(select(Summary)).all() == []
    assert session.get(Run, out.run_id).error_kind == "http_529"


def test_ai_recovers_on_retry(session):
    ai = FakeSummarizer([retryable_error(), ok_response(["src/app.py"])])
    out = summarize_diff(session, ai, make_diff("src/app.py"))
    assert out.status == "done"
    assert len(ai.calls) == 2


def test_non_retryable_error_is_not_retried_but_usage_is_recorded(session):
    usage = TokenUsage("claude-opus-5-5", 500, 0)
    ai = FakeSummarizer([AIError("refusal", retryable=False, usage=usage)])
    out = summarize_diff(session, ai, make_diff("src/app.py"))
    assert out.status == "failed"
    assert len(ai.calls) == 1
    assert session.scalars(select(Usage)).one().input_tokens == 500


def test_unexpected_exception_fails_safely(session):
    ai = FakeSummarizer([RuntimeError("boom")])
    out = summarize_diff(session, ai, make_diff("src/app.py"))
    assert (out.status, out.message) == ("failed", FAILED_MESSAGE)


def test_only_lockfiles_makes_no_ai_call(session):
    ai = FakeSummarizer()
    out = summarize_diff(session, ai, make_diff("package-lock.json"))
    assert out.status == "skipped"
    assert out.message.startswith("Nothing to summarize")
    assert ai.calls == []


def test_too_many_files_makes_no_ai_call(session):
    ai = FakeSummarizer()
    out = summarize_diff(session, ai, make_diff(*[f"f{i}.py" for i in range(101)]))
    assert out.status == "skipped"
    assert ai.calls == []


def test_no_api_key_fails_without_call(session):
    out = summarize_diff(session, None, make_diff("src/app.py"))
    assert out.status == "failed"
    assert session.get(Run, out.run_id).error_kind == "no_api_key"


def test_monthly_spend_cap_stops_before_calling_ai(session):
    run = Run(source="dev_paste", status="done")
    session.add(run)
    session.flush()
    session.add(Usage(run_id=run.id, model="m", input_tokens=0, output_tokens=0,
                      cost_microusd=10_000_000))  # fmt: skip
    session.commit()
    ai = FakeSummarizer()

    out = summarize_diff(session, ai, make_diff("src/app.py"), spend_cap_usd=10.0)

    assert out.status == "capped"
    assert "$10" in out.message
    assert ai.calls == []


def test_month_spend_ignores_last_month(session):
    from datetime import datetime

    run = Run(source="dev_paste", status="done")
    session.add(run)
    session.flush()
    session.add(
        Usage(
            run_id=run.id,
            model="m",
            input_tokens=0,
            output_tokens=0,
            cost_microusd=9_000_000,
            created_at=datetime(2026, 10, 31, 23, 59),
        )
    )
    session.add(Usage(run_id=run.id, model="m", input_tokens=0, output_tokens=0,
                      cost_microusd=1_000, created_at=datetime(2026, 11, 2)))  # fmt: skip
    session.commit()
    assert month_spend_microusd(session, now=datetime(2026, 11, 17)) == 1_000

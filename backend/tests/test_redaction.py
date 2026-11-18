import json
import logging

import pytest
import structlog

from app.logging_setup import REDACTED, configure_logging, get_logger, redact, redact_string

PEM = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\nabc\n-----END RSA PRIVATE KEY-----"


@pytest.mark.parametrize(
    "key",
    [
        "password", "Password", "password_hash", "token", "access_token", "client_secret",
        "webhook_secret", "github_app_private_key", "authorization", "Cookie", "set-cookie",
        "csrf", "diff", "patch", "comment_markdown", "gemini_api_key", "session",
    ],
)  # fmt: skip
def test_secret_keys_are_hidden(key):
    assert redact({key: "value-123"}) == {key: REDACTED}


def test_normal_keys_are_kept():
    data = {
        "status_code": 200,
        "method": "GET",
        "path": "/api/runs",
        "user_id": 7,
        "model": "gemini-3.8-flash",
        "files_read": 13,
        "rate_limit_remaining": 4999,
    }
    assert redact(data) == data


def test_nested_and_lists():
    out = redact(
        {"headers": {"Authorization": "Bearer abc", "accept": "json"}, "items": [{"token": "x"}]}
    )
    assert out == {
        "headers": {"Authorization": REDACTED, "accept": "json"},
        "items": [{"token": REDACTED}],
    }


@pytest.mark.parametrize(
    "secret",
    [
        "ghs_" + "a" * 36,
        "gho_" + "b" * 36,
        "github_pat_" + "c" * 40,
        "eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiIxMjMifQ.c2lnbmF0dXJlc2lnbmF0dXJl",
        "sk-ant-api03-" + "d" * 30,
        "AIza" + "e" * 35,
        "AQ." + "f" * 50,
        PEM,
    ],
)
def test_credentials_inside_strings_are_masked(secret):
    text = f"GitHub said no for {secret} at 12:00"
    out = redact_string(text)
    assert secret not in out
    assert REDACTED in out
    assert out.startswith("GitHub said no for")


def test_bearer_header_and_query_params_and_db_url():
    assert "abcdef123456" not in redact_string("Authorization: Bearer abcdef123456")
    assert (
        redact_string("https://x/cb?client_secret=s3cr3t&x=1")
        == f"https://x/cb?client_secret={REDACTED}&x=1"
    )
    out = redact_string("postgresql+psycopg://pr:hunter2@db:5432/pr")
    assert "hunter2" not in out and out.startswith("postgresql+psycopg://pr:")


def test_full_pipeline_writes_json_without_secrets(capsys):
    configure_logging("INFO")
    structlog.contextvars.bind_contextvars(request_id="req-1")
    try:
        get_logger("test").info(
            "login_failed", email="a@b.co", password="hunter2", note="token ghs_" + "z" * 36
        )
        logging.getLogger("uvicorn.error").warning("third-party line with Bearer zzzzzzzzzzzz")
    finally:
        structlog.contextvars.clear_contextvars()
    lines = [json.loads(x) for x in capsys.readouterr().out.strip().splitlines()]
    ours, theirs = lines[-2], lines[-1]
    assert (
        ours["event"] == "login_failed"
        and ours["request_id"] == "req-1"
        and ours["level"] == "info"
    )
    assert ours["password"] == REDACTED
    assert "ghs_" not in ours["note"]
    assert "zzzzzzzzzzzz" not in theirs["event"]


def test_exceptions_are_logged_without_local_variables(capsys):
    configure_logging("INFO")

    def boom():
        password = "hunter2"  # noqa: F841, S105
        raise RuntimeError("bad thing")

    try:
        boom()
    except RuntimeError:
        get_logger("test").exception("unhandled_error")
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["exception"][0]["exc_type"] == "RuntimeError"
    assert "hunter2" not in json.dumps(line)

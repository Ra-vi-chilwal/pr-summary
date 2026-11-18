"""Structured JSON logging with secret redaction.

Every log line (ours and uvicorn's) goes through the same chain:
contextvars (request_id, user_id) -> level/time -> exception as structured dict (no locals)
-> REDACTION -> JSON. Never log passwords, tokens, cookies, private keys or diff contents;
the redactor is the safety net, not permission.
"""

import logging
import re
import sys
from typing import Any

import structlog
from structlog.tracebacks import ExceptionDictTransformer

REDACTED = "[REDACTED]"

# Keys whose values are always hidden, at any depth.
_SECRET_KEYS = {
    "password", "passwd", "new_password", "password_hash", "token", "access_token",
    "refresh_token", "id_token", "secret", "client_secret", "webhook_secret", "api_key",
    "apikey", "authorization", "cookie", "cookies", "set-cookie", "session", "csrf",
    "csrf_token", "private_key", "jwt", "signature", "x-hub-signature-256", "diff", "patch",
    "diff_text", "code", "body", "content", "contents", "comment_markdown",
}  # fmt: skip
_SECRET_SUFFIXES = ("_token", "_secret", "_password", "_key", "_cookie", "_diff")

# Values that look like credentials, wherever they appear inside a string.
_SECRET_VALUE_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    re.compile(r"(?i)\b(bearer|token|basic)\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),  # JWT
    re.compile(r"\bsk-ant-[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\bAQ\.[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?i)(password|passwd|secret|api_key|client_secret)=([^&\s]+)"),
    re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?://[^:/\s]+:)([^@\s]+)(@)"),  # DB URL password
]


def _is_secret_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    k = key.lower()
    return k in _SECRET_KEYS or k.endswith(_SECRET_SUFFIXES)


def redact_string(value: str) -> str:
    for pattern in _SECRET_VALUE_PATTERNS:
        if pattern.groups == 3:  # keep scheme/user and host around the DB password
            value = pattern.sub(lambda m: f"{m.group(1)}{REDACTED}{m.group(3)}", value)
        elif pattern.groups == 2 and "=" in pattern.pattern:
            value = pattern.sub(lambda m: f"{m.group(1)}={REDACTED}", value)
        else:
            value = pattern.sub(REDACTED, value)
    return value


def redact(value: Any, _depth: int = 0) -> Any:
    """Return a copy with secret keys hidden and credential-looking strings masked."""
    if _depth > 8:
        return REDACTED
    if isinstance(value, dict):
        return {
            k: (REDACTED if _is_secret_key(k) and v not in (None, "") else redact(v, _depth + 1))
            for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return type(value)(redact(v, _depth + 1) for v in value)
    if isinstance(value, str):
        return redact_string(value)
    return value


def redact_processor(_logger: Any, _method: str, event_dict: dict) -> dict:
    return redact(event_dict)


def configure_logging(level: str = "INFO", json_output: bool = True) -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    pre_chain = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
    ]
    renderer = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    exceptions = structlog.processors.ExceptionRenderer(ExceptionDictTransformer(show_locals=False))

    structlog.configure(
        processors=[*pre_chain, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=pre_chain,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            exceptions,
            redact_processor,
            renderer,
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())

    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
    logging.getLogger("uvicorn.access").disabled = True  # our middleware logs requests
    # HTTP client libraries log full URLs at INFO; keep them quiet.
    for noisy in ("httpx", "httpx2", "httpcore", "google_genai", "anthropic", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str = "pr_summary") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)

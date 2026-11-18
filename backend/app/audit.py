"""Security audit trail: a row in audit_log plus a structured log line.

Events: signup, login, login_failed, logout, github_connected, github_disconnected,
github_repos_changed, summary_posted, summary_post_failed.
"""

from fastapi import Request
from sqlalchemy.orm import Session

from app.logging_setup import get_logger, redact
from app.models import AuditLog

log = get_logger("pr_summary.audit")


def client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    # Render and most proxies put the real client first in X-Forwarded-For.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return request.client.host[:64] if request.client else None


def record(
    session: Session,
    event: str,
    *,
    user_id: int | None = None,
    request: Request | None = None,
    commit: bool = True,
    **detail: object,
) -> None:
    safe = redact(detail)
    request_id = getattr(request.state, "request_id", None) if request else None
    session.add(
        AuditLog(
            event=event,
            user_id=user_id,
            ip=client_ip(request),
            request_id=request_id,
            detail=safe,
        )
    )
    if commit:
        session.commit()
    log.info("audit", audit_event=event, user_id=user_id, **safe)

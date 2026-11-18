"""Passwords, sessions, CSRF and signed cookies.

- Passwords: argon2id (argon2-cffi defaults).
- Sessions: a random 256-bit token in an httpOnly, Secure, SameSite=Lax cookie. The DB stores
  only its SHA-256, so a database leak doesn't hand out live sessions.
- CSRF: double-submit token. A readable `prs_csrf` cookie must match the X-CSRF-Token header
  on every state-changing /api request (except the GitHub webhook, which is signed).
"""

import base64
import hashlib
import hmac
import json
import secrets
from datetime import timedelta

import structlog
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import client_ip
from app.config import Settings
from app.db import get_session
from app.models import AuthSession, User, utcnow

SESSION_COOKIE = "prs_session"
CSRF_COOKIE = "prs_csrf"
CSRF_HEADER = "x-csrf-token"
STATE_COOKIE = "prs_oauth_state"
ANON_RUNS_COOKIE = "prs_anon_runs"

_hasher = PasswordHasher()
# Verifying against this when the email is unknown keeps response times similar.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


# ------------------------------------------------------------------ passwords
def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and bool(password_hash)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


COMMON_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789", "1234567890",
    "qwerty123", "qwertyuiop", "iloveyou", "letmein123", "admin1234", "welcome123",
}  # fmt: skip


def password_problem(password: str, email: str = "") -> str | None:
    """Server-side rule (the frontend shows the same rule as a hint)."""
    if len(password) < 10:
        return "Use at least 10 characters."
    if len(password) > 128:
        return "Use 128 characters or fewer."
    if password.lower() in COMMON_PASSWORDS or len(set(password)) < 4:
        return "That password is too easy to guess. Try a short sentence."
    if email and password.lower() == email.lower():
        return "Your password can't be your email address."
    return None


# ------------------------------------------------------------------ tokens & signing
def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def sign(settings_secret: str, payload: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    mac = hmac.new(settings_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{mac}"


def unsign(settings_secret: str, value: str | None) -> dict | None:
    if not value or "." not in value:
        return None
    body, mac = value.rsplit(".", 1)
    good = hmac.new(settings_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, good):
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(body.encode()))
    except ValueError:
        return None


def safe_next(path: str | None, default: str = "/dashboard") -> str:
    """Only same-site paths, never //evil.com or https://..."""
    if not path or not path.startswith("/") or path.startswith("//") or "\\" in path:
        return default
    return path


# ------------------------------------------------------------------ cookies
def _cookie_kwargs(settings: Settings, http_only: bool = True) -> dict:
    return {"httponly": http_only, "secure": settings.cookie_secure, "samesite": "lax", "path": "/"}


def set_session_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE, token, max_age=settings.session_days * 86400, **_cookie_kwargs(settings)
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(SESSION_COOKIE, **_cookie_kwargs(settings))


def ensure_csrf_cookie(request: Request, response: Response, settings: Settings) -> None:
    if not request.cookies.get(CSRF_COOKIE):
        response.set_cookie(
            CSRF_COOKIE,
            new_token(),
            max_age=30 * 86400,
            **_cookie_kwargs(settings, http_only=False),
        )


def csrf_ok(request: Request) -> bool:
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get(CSRF_HEADER)
    return bool(cookie and header and hmac.compare_digest(cookie, header))


# ------------------------------------------------------------------ sessions
def create_session(
    db: Session, user: User, request: Request, response: Response, settings: Settings
) -> None:
    token = new_token()
    now = utcnow()
    db.add(
        AuthSession(
            token_hash=token_hash(token),
            user_id=user.id,
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(days=settings.session_days),
            ip=client_ip(request),
            user_agent=(request.headers.get("user-agent") or "")[:300],
        )
    )
    user.last_login_at = now
    db.commit()
    set_session_cookie(response, settings, token)


def end_session(db: Session, request: Request) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        row = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(token)))
        if row:
            db.delete(row)
            db.commit()


def optional_user(request: Request, db: Session = Depends(get_session)) -> User | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    row = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(token)))
    now = utcnow()
    if row is None or row.expires_at <= now:
        return None
    user = db.get(User, row.user_id)
    if user is None:
        return None
    if now - row.last_seen_at > timedelta(minutes=5):
        row.last_seen_at = now
        db.commit()
    request.state.user_id = user.id
    structlog.contextvars.bind_contextvars(user_id=user.id)
    return user


def current_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    return user

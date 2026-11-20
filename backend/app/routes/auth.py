"""Sign up, log in, log out, who am I, and GitHub sign-in (which also links installations)."""

import re
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import audit
from app.db import get_session
from app.errors import FieldError
from app.github_app import GitHub, GitHubError
from app.logging_setup import get_logger
from app.models import GitHubInstallation, User, utcnow
from app.ratelimit import RateLimiter, limit
from app.security import (
    STATE_COOKIE,
    clear_session_cookie,
    create_session,
    end_session,
    hash_password,
    optional_user,
    password_problem,
    safe_next,
    sign,
    unsign,
    verify_password,
)

log = get_logger("pr_summary.auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
BAD_LOGIN = "Email or password is incorrect."
FAILED_LOGINS_PER_EMAIL = 5
FAILED_LOGIN_WINDOW_S = 15 * 60


class SignupIn(BaseModel):
    name: str = ""
    email: str = ""
    password: str = ""


class LoginIn(BaseModel):
    email: str = ""
    password: str = ""


class UserOut(BaseModel):
    id: int
    name: str
    email: str | None
    avatar_url: str | None
    github_login: str | None


class InstallationOut(BaseModel):
    installation_id: int
    account_login: str
    account_type: str
    repo_count: int | None
    manage_url: str


class MeOut(BaseModel):
    user: UserOut | None
    installations: list[InstallationOut]
    github_app_configured: bool
    github_login_configured: bool


def user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id, name=u.name, email=u.email, avatar_url=u.avatar_url, github_login=u.github_login
    )


def manage_url(inst: GitHubInstallation) -> str:
    if inst.account_type == "Organization":
        return f"https://github.com/organizations/{inst.account_login}/settings/installations/{inst.installation_id}"
    return f"https://github.com/settings/installations/{inst.installation_id}"


def active_installations(db: Session, user_id: int) -> list[GitHubInstallation]:
    return list(
        db.scalars(
            select(GitHubInstallation)
            .where(GitHubInstallation.user_id == user_id, GitHubInstallation.deleted_at.is_(None))
            .order_by(GitHubInstallation.id)
        )
    )


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


def build_router(github: GitHub) -> APIRouter:
    router = APIRouter(prefix="/api/auth", tags=["auth"])

    # ---------------------------------------------------------------- email + password
    @router.post("/signup", status_code=201)
    def signup(
        body: SignupIn, request: Request, response: Response, db: Session = Depends(get_session)
    ) -> dict:
        settings = request.app.state.settings
        limit(request, "signup", settings.auth_rate_limit, window_s=600)
        name, email = body.name.strip(), body.email.strip().lower()
        fields: dict[str, str] = {}
        if not name:
            fields["name"] = "Tell us what to call you."
        elif len(name) > 100:
            fields["name"] = "Use 100 characters or fewer."
        if not EMAIL_RE.match(email) or len(email) > 320:
            fields["email"] = "Enter an email address like name@example.com."
        problem = password_problem(body.password, email)
        if problem:
            fields["password"] = problem
        if fields:
            raise FieldError(422, "Check the highlighted fields.", fields)
        if db.scalar(select(User.id).where(func.lower(User.email) == email)):
            raise FieldError(
                409,
                "That email is already registered.",
                {"email": "That email is already registered. Try signing in instead."},
            )

        user = User(name=name, email=email, password_hash=hash_password(body.password))
        db.add(user)
        db.commit()
        audit.record(db, "signup", user_id=user.id, request=request, method="password")
        create_session(db, user, request, response, settings)
        return {"user": user_out(user).model_dump()}

    @router.post("/login")
    def login(
        body: LoginIn, request: Request, response: Response, db: Session = Depends(get_session)
    ) -> dict:
        settings = request.app.state.settings
        limit(request, "login", settings.auth_rate_limit, window_s=600)
        email = body.email.strip().lower()
        if not email or not body.password:
            fields = {}
            if not email:
                fields["email"] = "Enter your email."
            if not body.password:
                fields["password"] = "Enter your password."  # noqa: S105
            raise FieldError(422, "Check the highlighted fields.", fields)

        limiter: RateLimiter = request.app.state.limiter
        fail_key = f"login_fail:{email}"
        if limiter.count(fail_key, FAILED_LOGIN_WINDOW_S) >= FAILED_LOGINS_PER_EMAIL:
            audit.record(db, "login_blocked", request=request, email=mask_email(email))
            raise FieldError(429, "Too many failed attempts for this email. Wait 15 minutes.", {})

        user = db.scalar(select(User).where(func.lower(User.email) == email))
        if not verify_password(user.password_hash if user else None, body.password):
            limiter.hit(fail_key, 10_000, FAILED_LOGIN_WINDOW_S)
            audit.record(
                db,
                "login_failed",
                user_id=user.id if user else None,
                request=request,
                email=mask_email(email),
            )
            raise FieldError(401, BAD_LOGIN, {"password": BAD_LOGIN})

        limiter.reset(fail_key)
        audit.record(db, "login", user_id=user.id, request=request, method="password")
        create_session(db, user, request, response, settings)
        return {"user": user_out(user).model_dump()}

    @router.post("/logout", status_code=204)
    def logout(
        request: Request,
        response: Response,
        db: Session = Depends(get_session),
        user: User | None = Depends(optional_user),
    ) -> Response:
        end_session(db, request)
        if user:
            audit.record(db, "logout", user_id=user.id, request=request)
        clear_session_cookie(response, request.app.state.settings)
        response.status_code = 204
        return response

    @router.get("/me", response_model=MeOut)
    def me(
        request: Request,
        db: Session = Depends(get_session),
        user: User | None = Depends(optional_user),
    ) -> MeOut:
        settings = request.app.state.settings
        installs = active_installations(db, user.id) if user else []
        return MeOut(
            user=user_out(user) if user else None,
            installations=[
                InstallationOut(
                    installation_id=i.installation_id,
                    account_login=i.account_login,
                    account_type=i.account_type,
                    repo_count=i.repo_count,
                    manage_url=manage_url(i),
                )
                for i in installs
            ],
            github_app_configured=settings.github_app_configured,
            github_login_configured=settings.github_login_configured,
        )

    # ---------------------------------------------------------------- GitHub sign-in
    def callback_url(request: Request) -> str:
        return f"{request.app.state.settings.app_base_url}/api/auth/github/callback"

    @router.get("/github/start")
    def github_start(request: Request, next: str | None = None) -> RedirectResponse:  # noqa: A002
        settings = request.app.state.settings
        if not settings.github_login_configured:
            return RedirectResponse("/login?error=github_unavailable", status_code=303)
        state = secrets.token_urlsafe(24)
        resp = RedirectResponse(github.authorize_url(state, callback_url(request)), status_code=303)
        set_state_cookie(resp, request, state, "login", safe_next(next))
        return resp

    @router.get("/github/callback")
    def github_callback(
        request: Request,
        code: str | None = None,
        state: str | None = None,
        installation_id: int | None = None,
        setup_action: str | None = None,
        db: Session = Depends(get_session),
        current: User | None = Depends(optional_user),
    ) -> RedirectResponse:
        settings = request.app.state.settings
        saved = unsign(settings.secret_key, request.cookies.get(STATE_COOKIE)) or {}
        installing = installation_id is not None
        # A normal sign-in must come back with the state we set. An install may also start on
        # GitHub's own page (no state); then the user token check below is what protects us.
        if not code or (not installing and (not state or state != saved.get("state"))):
            log.warning("github_callback_rejected", reason="state" if code else "no_code")
            return _done(request, "/login?error=github_failed")
        next_path = safe_next(saved.get("next"), "/dashboard")
        # Only trusted when the state matched (checked above for every non-install callback).
        linking = not installing and saved.get("purpose") == "link"

        try:
            user_token = github.exchange_code(code, callback_url(request))
            gh_user = github.get_user(user_token)
            user = _find_or_create_user(
                db, request, gh_user, github.verified_emails(user_token), current
            )
            if installing:
                visible = github.user_installation_ids(user_token)
                if installation_id not in visible:
                    log.warning("github_install_not_visible_to_user")
                    return _done(request, "/dashboard?github=not_yours")
                _link_installation(db, request, github, user, installation_id)
                next_path = "/dashboard?github=connected"
            elif linking:
                result = _link_visible_installations(db, request, github, user, user_token)
                next_path = f"/dashboard?github={result}"
        except GitHubError as e:
            log.warning("github_callback_failed", kind=e.kind, linking=linking)
            failed = "/dashboard?github=link_failed" if linking else "/login?error=github_failed"
            return _done(request, failed)

        resp = _done(request, next_path)
        if current is None or current.id != user.id:
            create_session(db, user, request, resp, settings)
            audit.record(db, "login", user_id=user.id, request=request, method="github")
        return resp

    return router


# ---------------------------------------------------------------- helpers
def set_state_cookie(
    resp: Response, request: Request, state: str, purpose: str, next_path: str
) -> None:
    settings = request.app.state.settings
    value = sign(settings.secret_key, {"state": state, "purpose": purpose, "next": next_path})
    resp.set_cookie(
        STATE_COOKIE, value, max_age=600, httponly=True, secure=settings.cookie_secure,
        samesite="lax", path="/api/auth/github",
    )  # fmt: skip


def _done(request: Request, path: str) -> RedirectResponse:
    resp = RedirectResponse(path, status_code=303)
    resp.delete_cookie(STATE_COOKIE, path="/api/auth/github")
    return resp


def _find_or_create_user(
    db: Session, request: Request, gh: dict, emails: list[str], current: User | None
) -> User:
    gh_id = int(gh["id"])
    user = db.scalar(select(User).where(User.github_user_id == gh_id))
    if user is None and current is not None and current.github_user_id is None:
        user = current  # signed in with email: link this GitHub account to it
    if user is None and emails:
        # Only link by email when GitHub says the address is verified.
        user = db.scalar(
            select(User).where(func.lower(User.email).in_(emails), User.github_user_id.is_(None))
        )
    if user is None:
        email = emails[0] if emails else None
        if email and db.scalar(select(User.id).where(func.lower(User.email) == email)):
            email = None
        user = User(name=(gh.get("name") or gh.get("login") or "GitHub user")[:100], email=email)
        db.add(user)
        audit.record(db, "signup", request=request, commit=False, method="github")
    user.github_user_id = gh_id
    user.github_login = gh.get("login")
    user.avatar_url = gh.get("avatar_url")
    db.commit()
    return user


def _link_installation(
    db: Session, request: Request, github: GitHub, user: User, installation_id: int
) -> None:
    info = github.get_installation(installation_id)
    account = info.get("account") or {}
    inst = db.scalar(
        select(GitHubInstallation).where(GitHubInstallation.installation_id == installation_id)
    )
    if inst is None:
        inst = GitHubInstallation(installation_id=installation_id, account_login="")
        db.add(inst)
    inst.user_id = user.id
    inst.account_login = account.get("login") or ""
    inst.account_type = account.get("type") or "User"
    inst.account_id = account.get("id")
    inst.repository_selection = info.get("repository_selection")
    inst.deleted_at = None
    inst.updated_at = utcnow()
    try:
        _, inst.repo_count = github.list_installation_repos(installation_id, max_pages=1)
    except GitHubError:
        inst.repo_count = None
    db.commit()
    audit.record(
        db, "github_connected", user_id=user.id, request=request,
        installation_id=installation_id, account=inst.account_login,
    )  # fmt: skip


def _link_visible_installations(
    db: Session, request: Request, github: GitHub, user: User, user_token: str
) -> str:
    """Link every installation of this app that GitHub shows this person, unless another
    account here already owns it. Returns the dashboard notice key."""
    visible = github.user_installation_ids(user_token)
    if not visible:
        log.info("github_link_none_found")
        return "none_found"
    owners = {
        row.installation_id: row.user_id
        for row in db.scalars(
            select(GitHubInstallation).where(
                GitHubInstallation.installation_id.in_(visible),
                GitHubInstallation.deleted_at.is_(None),
            )
        )
    }
    linked = 0
    for inst_id in sorted(visible):
        if owners.get(inst_id) not in (None, user.id):
            continue  # claimed by a different account here; never take it over
        _link_installation(db, request, github, user, inst_id)
        linked += 1
    log.info("github_link_done", visible=len(visible), linked=linked)
    return "connected" if linked else "linked_elsewhere"


def login_redirect_url(error: str) -> str:
    return f"/login?{urlencode({'error': error})}"

"""GitHub App: install, repos, PRs, summarize from the dashboard, and the webhook."""

import json
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.db import get_session
from app.github_app import GitHub, GitHubError, verify_webhook_signature
from app.logging_setup import get_logger
from app.models import GitHubInstallation, User, utcnow
from app.pr_bot import PREvent, handle_pull_request, upsert_repo
from app.routes.auth import active_installations, set_state_cookie
from app.routes.summaries import SummarizeOut, outcome_out
from app.security import current_user
from app.service import summarize_diff

log = get_logger("pr_summary.github")

PR_ACTIONS = {"opened", "synchronize", "reopened", "ready_for_review"}


class RepoOut(BaseModel):
    full_name: str
    owner: str
    name: str
    private: bool
    installation_id: int
    updated_at: str | None


class PullOut(BaseModel):
    number: int
    title: str
    author: str | None
    updated_at: str
    draft: bool
    html_url: str


def gh_http_error(e: GitHubError) -> HTTPException:
    status = {"rate_limited": 429, "uninstalled": 409, "no_access": 403, "too_large": 413}.get(
        e.kind, 502
    )
    return HTTPException(status_code=status, detail=e.message)


def installation_for(db: Session, github: GitHub, user: User, owner: str, repo: str) -> int:
    """The user's installation that covers owner/repo, or a clear 403."""
    mine = {i.installation_id for i in active_installations(db, user.id)}
    if not mine:
        raise HTTPException(status_code=409, detail="Connect GitHub first.")
    try:
        inst = github.repo_installation_id(owner, repo)
    except GitHubError as e:
        raise gh_http_error(e) from e
    if inst is None or inst not in mine:
        raise HTTPException(
            status_code=403,
            detail="Your GitHub connection doesn't include this repository. "
            "Add it in the installation settings.",
        )
    return inst


def build_router(github: GitHub) -> APIRouter:
    router = APIRouter(prefix="/api/github", tags=["github"])

    @router.get("/install")
    def install(request: Request, user: User = Depends(current_user)) -> RedirectResponse:
        if not request.app.state.settings.github_app_configured:
            return RedirectResponse("/dashboard?github=unconfigured", status_code=303)
        state = secrets.token_urlsafe(24)
        resp = RedirectResponse(github.install_url(state), status_code=303)
        set_state_cookie(resp, request, state, "install", "/dashboard")
        return resp

    @router.get("/repos")
    def repos(db: Session = Depends(get_session), user: User = Depends(current_user)) -> dict:
        out: list[RepoOut] = []
        for inst in active_installations(db, user.id):
            try:
                items, total = github.list_installation_repos(inst.installation_id)
            except GitHubError as e:
                if e.kind == "uninstalled":
                    inst.deleted_at = utcnow()
                    db.commit()
                    audit.record(
                        db,
                        "github_disconnected",
                        user_id=user.id,
                        installation_id=inst.installation_id,
                        reason="token_rejected",
                    )
                    raise HTTPException(status_code=409, detail=e.message) from e
                raise gh_http_error(e) from e
            if inst.repo_count != total:
                inst.repo_count = total
                db.commit()
            out += [
                RepoOut(
                    full_name=r["full_name"],
                    owner=r["owner"]["login"],
                    name=r["name"],
                    private=bool(r.get("private")),
                    installation_id=inst.installation_id,
                    updated_at=r.get("pushed_at") or r.get("updated_at"),
                )
                for r in items
            ]
        out.sort(key=lambda r: r.updated_at or "", reverse=True)
        return {"repos": [r.model_dump() for r in out]}

    @router.get("/repos/{owner}/{repo}/pulls")
    def pulls(
        owner: str,
        repo: str,
        db: Session = Depends(get_session),
        user: User = Depends(current_user),
    ) -> dict:
        inst = installation_for(db, github, user, owner, repo)
        try:
            items = github.list_open_pulls(inst, owner, repo)
        except GitHubError as e:
            raise gh_http_error(e) from e
        return {
            "pulls": [
                PullOut(
                    number=p["number"],
                    title=p["title"],
                    author=(p.get("user") or {}).get("login"),
                    updated_at=p["updated_at"],
                    draft=bool(p.get("draft")),
                    html_url=p["html_url"],
                ).model_dump()
                for p in items
            ]
        }

    @router.post("/repos/{owner}/{repo}/pulls/{number}/summarize", response_model=SummarizeOut)
    def summarize_pull(
        owner: str,
        repo: str,
        number: int,
        request: Request,
        db: Session = Depends(get_session),
        user: User = Depends(current_user),
    ) -> SummarizeOut:
        settings = request.app.state.settings
        inst = installation_for(db, github, user, owner, repo)
        try:
            pr = github.get_pull(inst, owner, repo, number)
            diff = github.get_pull_diff(inst, owner, repo, number)
        except GitHubError as e:
            raise gh_http_error(e) from e
        repo_row = upsert_repo(
            db, (pr.get("base") or {}).get("repo", {}).get("id"), f"{owner}/{repo}"
        )
        outcome = summarize_diff(
            db, request.app.state.summarizer, diff, pr.get("title") or "",
            settings.monthly_spend_cap_usd, user_id=user.id, repo_id=repo_row.id,
            pr_number=number, commit_sha=(pr.get("head") or {}).get("sha"), source="dashboard",
        )  # fmt: skip
        return outcome_out(outcome, diff, pr.get("title") or "")

    # ---------------------------------------------------------------- webhook
    @router.post("/webhook")
    async def webhook(request: Request, background: BackgroundTasks) -> JSONResponse:
        settings = request.app.state.settings
        body = await request.body()
        event = request.headers.get("x-github-event", "")
        delivery = request.headers.get("x-github-delivery", "")
        if not verify_webhook_signature(
            settings.github_webhook_secret, body, request.headers.get("x-hub-signature-256")
        ):
            log.warning(
                "webhook_rejected", gh_event=event, delivery=delivery, reason="bad_signature"
            )
            return JSONResponse({"detail": "Invalid signature."}, status_code=401)
        try:
            payload = json.loads(body)
        except ValueError:
            return JSONResponse({"detail": "Invalid JSON."}, status_code=400)
        action = payload.get("action")
        log.info(
            "webhook_received", gh_event=event, action=action, delivery=delivery, verified=True
        )

        factory = request.app.state.session_factory
        if event == "installation":
            with factory() as db:
                _on_installation(db, github, request, payload)
        elif event == "installation_repositories":
            with factory() as db:
                _on_installation_repos(db, request, payload)
        elif event == "pull_request" and action in PR_ACTIONS:
            pr = payload["pull_request"]
            if pr.get("draft"):
                return JSONResponse({"ok": True, "skipped": "draft"}, status_code=202)
            ev = PREvent(
                installation_id=int(payload["installation"]["id"]),
                repo_github_id=int(payload["repository"]["id"]),
                owner=payload["repository"]["owner"]["login"],
                repo=payload["repository"]["name"],
                number=int(pr["number"]),
                head_sha=pr["head"]["sha"],
                title=pr.get("title") or "",
            )
            background.add_task(
                _run_pr_event, factory, github, request.app.state.summarizer, settings, ev
            )
            return JSONResponse({"ok": True, "queued": True}, status_code=202)
        return JSONResponse({"ok": True})

    return router


def _run_pr_event(factory, github, summarizer, settings, ev: PREvent) -> None:
    try:
        result = handle_pull_request(factory, github, summarizer, settings, ev)
        log.info("pr_event_done", result=result, repo=ev.full_name, pr=ev.number)
    except Exception:
        log.exception("pr_event_crashed", repo=ev.full_name, pr=ev.number)


def _on_installation(db: Session, github: GitHub, request: Request, payload: dict) -> None:
    action = payload.get("action")
    data = payload.get("installation") or {}
    inst_id = int(data["id"])
    account = data.get("account") or {}
    row = db.scalar(select(GitHubInstallation).where(GitHubInstallation.installation_id == inst_id))
    if action == "created":
        if row is None:
            row = GitHubInstallation(
                installation_id=inst_id, account_login=account.get("login") or ""
            )
            db.add(row)
        # Link to the installer if they already have an account here via GitHub sign-in.
        sender_id = (payload.get("sender") or {}).get("id")
        if row.user_id is None and sender_id:
            installer = db.scalar(select(User).where(User.github_user_id == int(sender_id)))
            row.user_id = installer.id if installer else None
        row.account_login = account.get("login") or row.account_login
        row.account_type = account.get("type") or "User"
        row.account_id = account.get("id")
        row.repository_selection = data.get("repository_selection")
        row.repo_count = len(payload.get("repositories") or []) or row.repo_count
        row.deleted_at = None
        row.updated_at = utcnow()
        db.commit()
        audit.record(db, "github_connected", user_id=row.user_id, request=request,
                     installation_id=inst_id, account=row.account_login, via="webhook")  # fmt: skip
    elif action == "deleted" and row is not None:
        row.deleted_at = utcnow()
        db.commit()
        github.forget_installation(inst_id)
        audit.record(db, "github_disconnected", user_id=row.user_id, request=request,
                     installation_id=inst_id, account=row.account_login)  # fmt: skip
    elif action in ("suspend", "unsuspend") and row is not None:
        row.suspended_at = utcnow() if action == "suspend" else None
        db.commit()
        github.forget_installation(inst_id)


def _on_installation_repos(db: Session, request: Request, payload: dict) -> None:
    inst_id = int(payload["installation"]["id"])
    row = db.scalar(select(GitHubInstallation).where(GitHubInstallation.installation_id == inst_id))
    if row is None:
        return
    added = len(payload.get("repositories_added") or [])
    removed = len(payload.get("repositories_removed") or [])
    if row.repo_count is not None:
        row.repo_count = max(0, row.repo_count + added - removed)
    row.repository_selection = payload.get("repository_selection") or row.repository_selection
    row.updated_at = utcnow()
    db.commit()
    audit.record(db, "github_repos_changed", user_id=row.user_id, request=request,
                 installation_id=inst_id, added=added, removed=removed)  # fmt: skip

"""GitHub: the App (JWT -> installation tokens -> REST) and user sign-in (OAuth).

Installation tokens are cached in memory until shortly before they expire and never leave
the backend. Every call is logged with its endpoint template, status, duration and
rate-limit remaining; tokens and bodies are never logged.
"""

import hashlib
import hmac
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlencode

import httpx2
import jwt

from app.config import Settings
from app.logging_setup import get_logger

log = get_logger("pr_summary.github")

API = "https://api.github.com"
WEB = "https://github.com"
API_VERSION = "2022-11-28"


@dataclass
class GitHubError(Exception):
    """kind is stable for code; message is safe to show to users."""

    kind: str  # uninstalled | no_access | rate_limited | too_large | not_found | unavailable | auth
    message: str
    status: int | None = None

    def __str__(self) -> str:
        return self.message


def verify_webhook_signature(secret: str | None, body: bytes, header: str | None) -> bool:
    """X-Hub-Signature-256 = 'sha256=' + HMAC-SHA256(secret, raw body). Constant-time compare."""
    if not secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header.removeprefix("sha256="), expected)


class GitHub:
    def __init__(self, settings: Settings, http: httpx2.Client | None = None):
        self.settings = settings
        self.http = http or httpx2.Client(
            timeout=20, headers={"User-Agent": "pr-summary", "X-GitHub-Api-Version": API_VERSION}
        )
        self._tokens: dict[int, tuple[str, float]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ plumbing
    def _call(
        self,
        method: str,
        url: str,
        endpoint: str,
        *,
        token: str | None = None,
        bearer_jwt: str | None = None,
        accept: str = "application/vnd.github+json",
        json: dict | None = None,
        data: dict | None = None,
        params: dict | None = None,
        ok: tuple[int, ...] = (200, 201),
        context: str = "repo",
    ) -> httpx2.Response:
        headers = {"Accept": accept}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif bearer_jwt:
            headers["Authorization"] = f"Bearer {bearer_jwt}"
        started = time.perf_counter()
        try:
            resp = self.http.request(
                method, url, headers=headers, json=json, data=data, params=params
            )
        except httpx2.HTTPError as e:
            log.warning(
                "github_call", endpoint=endpoint, error="network", error_type=type(e).__name__
            )
            raise GitHubError("unavailable", "Couldn't reach GitHub. Try again in a minute.") from e
        remaining = resp.headers.get("x-ratelimit-remaining")
        log.info(
            "github_call",
            endpoint=endpoint,
            status=resp.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000),
            rate_limit_remaining=int(remaining) if remaining and remaining.isdigit() else None,
        )
        if resp.status_code in ok:
            return resp
        raise self._error(resp, context)

    @staticmethod
    def _error(resp: httpx2.Response, context: str) -> GitHubError:
        status = resp.status_code
        if status == 429 or (status == 403 and resp.headers.get("x-ratelimit-remaining") == "0"):
            reset = resp.headers.get("x-ratelimit-reset")
            minutes = (
                max(1, round((int(reset) - time.time()) / 60))
                if reset and reset.isdigit()
                else None
            )
            when = f"in about {minutes} min" if minutes else "in a few minutes"
            return GitHubError(
                "rate_limited", f"GitHub's rate limit was reached. Try again {when}.", status
            )
        if context == "installation" and status in (401, 403, 404):
            return GitHubError(
                "uninstalled",
                "The GitHub App is no longer installed on this account. Connect GitHub again.",
                status,
            )
        if context == "diff" and status in (406, 422):
            return GitHubError(
                "too_large", "This pull request is too large for GitHub to send as a diff.", status
            )
        if status in (403, 404):
            return GitHubError(
                "no_access",
                "The app can't see this repository. Check its repository access in GitHub.",
                status,
            )
        if status == 401:
            return GitHubError("auth", "GitHub didn't accept our credentials. Try again.", status)
        return GitHubError(
            "unavailable", "GitHub returned an error. Try again in a minute.", status
        )

    # ------------------------------------------------------------------ app auth
    def app_jwt(self, now: float | None = None) -> str:
        if not self.settings.github_app_configured:
            raise GitHubError("unavailable", "The GitHub App isn't configured on this server.")
        now = int(now if now is not None else time.time())
        # iat is backdated 60s for clock drift; GitHub allows at most 10 minutes.
        payload = {"iat": now - 60, "exp": now + 540, "iss": str(self.settings.github_app_id)}
        return jwt.encode(payload, self.settings.private_key_pem, algorithm="RS256")

    def installation_token(self, installation_id: int) -> str:
        with self._lock:
            cached = self._tokens.get(installation_id)
            if cached and cached[1] - time.time() > 60:
                return cached[0]
        resp = self._call(
            "POST",
            f"{API}/app/installations/{installation_id}/access_tokens",
            "POST /app/installations/{id}/access_tokens",
            bearer_jwt=self.app_jwt(),
            ok=(201,),
            context="installation",
        )
        data = resp.json()
        expires = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
        with self._lock:
            self._tokens[installation_id] = (data["token"], expires.astimezone(UTC).timestamp())
        return data["token"]

    def forget_installation(self, installation_id: int) -> None:
        with self._lock:
            self._tokens.pop(installation_id, None)

    def get_installation(self, installation_id: int) -> dict:
        return self._call(
            "GET",
            f"{API}/app/installations/{installation_id}",
            "GET /app/installations/{id}",
            bearer_jwt=self.app_jwt(),
            context="installation",
        ).json()

    def repo_installation_id(self, owner: str, repo: str) -> int | None:
        """Which installation (if any) covers this repo."""
        try:
            resp = self._call(
                "GET",
                f"{API}/repos/{owner}/{repo}/installation",
                "GET /repos/{owner}/{repo}/installation",
                bearer_jwt=self.app_jwt(),
            )
        except GitHubError as e:
            if e.kind == "no_access":
                return None
            raise
        return int(resp.json()["id"])

    # ------------------------------------------------------------------ installation calls
    def list_installation_repos(
        self, installation_id: int, max_pages: int = 5
    ) -> tuple[list[dict], int]:
        token = self.installation_token(installation_id)
        repos: list[dict] = []
        total = 0
        for page in range(1, max_pages + 1):
            data = self._call(
                "GET",
                f"{API}/installation/repositories",
                "GET /installation/repositories",
                token=token,
                params={"per_page": 100, "page": page},
                context="installation",
            ).json()
            total = data.get("total_count", 0)
            repos.extend(data.get("repositories", []))
            if len(repos) >= total or not data.get("repositories"):
                break
        return repos, total

    def list_open_pulls(self, installation_id: int, owner: str, repo: str) -> list[dict]:
        return self._call(
            "GET",
            f"{API}/repos/{owner}/{repo}/pulls",
            "GET /repos/{owner}/{repo}/pulls",
            token=self.installation_token(installation_id),
            params={"state": "open", "per_page": 50, "sort": "updated", "direction": "desc"},
        ).json()

    def get_pull(self, installation_id: int, owner: str, repo: str, number: int) -> dict:
        return self._call(
            "GET",
            f"{API}/repos/{owner}/{repo}/pulls/{number}",
            "GET /repos/{owner}/{repo}/pulls/{n}",
            token=self.installation_token(installation_id),
        ).json()

    def get_pull_diff(self, installation_id: int, owner: str, repo: str, number: int) -> str:
        return self._call(
            "GET",
            f"{API}/repos/{owner}/{repo}/pulls/{number}",
            "GET /repos/{owner}/{repo}/pulls/{n} (diff)",
            token=self.installation_token(installation_id),
            accept="application/vnd.github.diff",
            context="diff",
        ).text

    def find_bot_comment(
        self, installation_id: int, owner: str, repo: str, number: int, marker: str
    ) -> int | None:
        """Recover our comment id if we lost it (e.g. a fresh database)."""
        bot_login = f"{self.settings.github_app_slug}[bot]"
        comments = self._call(
            "GET",
            f"{API}/repos/{owner}/{repo}/issues/{number}/comments",
            "GET /repos/{owner}/{repo}/issues/{n}/comments",
            token=self.installation_token(installation_id),
            params={"per_page": 100},
        ).json()
        for c in comments:
            if (c.get("user") or {}).get("login") == bot_login and (c.get("body") or "").startswith(
                marker
            ):
                return int(c["id"])
        return None

    def create_comment(
        self, installation_id: int, owner: str, repo: str, number: int, body: str
    ) -> int:
        resp = self._call(
            "POST",
            f"{API}/repos/{owner}/{repo}/issues/{number}/comments",
            "POST /repos/{owner}/{repo}/issues/{n}/comments",
            token=self.installation_token(installation_id),
            json={"body": body},
            ok=(201,),
        )
        return int(resp.json()["id"])

    def update_comment(
        self, installation_id: int, owner: str, repo: str, comment_id: int, body: str
    ) -> None:
        self._call(
            "PATCH",
            f"{API}/repos/{owner}/{repo}/issues/comments/{comment_id}",
            "PATCH /repos/{owner}/{repo}/issues/comments/{id}",
            token=self.installation_token(installation_id),
            json={"body": body},
        )

    # ------------------------------------------------------------------ user sign-in (OAuth)
    def install_url(self, state: str) -> str:
        query = urlencode({"state": state})
        return f"{WEB}/apps/{self.settings.github_app_slug}/installations/new?{query}"

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        q = {
            "client_id": self.settings.github_client_id,
            "redirect_uri": redirect_uri,
            "state": state,
        }
        return f"{WEB}/login/oauth/authorize?{urlencode(q)}"

    def exchange_code(self, code: str, redirect_uri: str) -> str:
        resp = self._call(
            "POST",
            f"{WEB}/login/oauth/access_token",
            "POST /login/oauth/access_token",
            accept="application/json",
            data={
                "client_id": self.settings.github_client_id,
                "client_secret": self.settings.github_client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            context="oauth",
        )
        token = resp.json().get("access_token")
        if not token:
            raise GitHubError("auth", "GitHub sign-in didn't complete. Try again.")
        return token

    def get_user(self, user_token: str) -> dict:
        return self._call(
            "GET", f"{API}/user", "GET /user", token=user_token, context="oauth"
        ).json()

    def verified_emails(self, user_token: str) -> list[str]:
        """Needs the App's 'Email addresses: read' permission; empty if not granted."""
        try:
            emails = self._call(
                "GET", f"{API}/user/emails", "GET /user/emails", token=user_token, context="oauth"
            ).json()
        except GitHubError:
            return []
        primary_first = sorted(emails, key=lambda e: not e.get("primary"))
        return [e["email"].lower() for e in primary_first if e.get("verified") and e.get("email")]

    def user_installation_ids(self, user_token: str) -> set[int]:
        data = self._call(
            "GET",
            f"{API}/user/installations",
            "GET /user/installations",
            token=user_token,
            params={"per_page": 100},
            context="oauth",
        ).json()
        return {int(i["id"]) for i in data.get("installations", [])}

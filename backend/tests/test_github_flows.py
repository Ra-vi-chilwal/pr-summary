"""End-to-end GitHub flows with a fake GitHub: OAuth, install linking, repos/PRs, webhooks."""

import hashlib
import hmac
import json

from sqlalchemy import select

from app.config import Settings
from app.github_app import GitHubError
from app.models import AuditLog, GitHubInstallation, PRComment, Run, User
from tests.helpers import FakeSummarizer, make_client, make_diff, ok_response, signup

SECRET = "whsec_test"
DIFF = make_diff("src/app.py")


class FakeGitHub:
    """Implements the GitHub methods the app uses; records writes."""

    def __init__(self, **kw):
        self.settings = Settings(
            github_app_id="1", github_app_slug="pr-summary", github_app_private_key="k",
            github_client_id="cid", github_client_secret="csecret", _env_file=None,
        )  # fmt: skip
        self.gh_user = {
            "id": 501,
            "login": "ravi",
            "name": "Ravi C",
            "avatar_url": "https://a/x.png",
        }
        self.emails = ["ravi@example.com"]
        self.visible_installations = {42}
        self.repo_installation = {"Ra-vi-chilwal/secret": 42}
        self.comments: dict[int, str] = {}
        self.created: list[int] = []
        self.updated: list[int] = []
        self.fail_diff: GitHubError | None = None
        self.fail_post: GitHubError | None = None
        self.diff = DIFF
        self.__dict__.update(kw)

    # sign-in
    def install_url(self, state):
        return f"https://github.com/apps/pr-summary/installations/new?state={state}"

    def authorize_url(self, state, redirect_uri):
        return f"https://github.com/login/oauth/authorize?state={state}"

    def exchange_code(self, code, redirect_uri):
        if code != "good-code":
            raise GitHubError("auth", "GitHub sign-in didn't complete. Try again.")
        return "gho_usertoken"

    def get_user(self, token):
        return self.gh_user

    def verified_emails(self, token):
        return self.emails

    def user_installation_ids(self, token):
        return self.visible_installations

    # app
    def get_installation(self, installation_id):
        return {
            "account": {"login": "Ra-vi-chilwal", "type": "User", "id": 9},
            "repository_selection": "selected",
        }

    def list_installation_repos(self, installation_id, max_pages=5):
        repos = [
            {"full_name": "Ra-vi-chilwal/secret", "name": "secret", "owner": {"login": "Ra-vi-chilwal"},
             "private": True, "pushed_at": "2026-11-17T10:00:00Z"},
            {"full_name": "Ra-vi-chilwal/open", "name": "open", "owner": {"login": "Ra-vi-chilwal"},
             "private": False, "pushed_at": "2026-11-10T10:00:00Z"},
        ]  # fmt: skip
        return repos, 2

    def repo_installation_id(self, owner, repo):
        return self.repo_installation.get(f"{owner}/{repo}")

    def list_open_pulls(self, inst, owner, repo):
        return [{"number": 3, "title": "Fix login", "user": {"login": "ravi"},
                 "updated_at": "2026-11-17T10:00:00Z", "draft": False, "html_url": "https://github.com/x"}]  # fmt: skip

    def get_pull(self, inst, owner, repo, number):
        return {"title": "Fix login", "head": {"sha": "abc123"}, "base": {"repo": {"id": 777}}}

    def get_pull_diff(self, inst, owner, repo, number):
        if self.fail_diff:
            raise self.fail_diff
        return self.diff

    def find_bot_comment(self, inst, owner, repo, number, marker):
        return None

    def create_comment(self, inst, owner, repo, number, body):
        if self.fail_post:
            raise self.fail_post
        cid = 1000 + len(self.created)
        self.created.append(cid)
        self.comments[cid] = body
        return cid

    def update_comment(self, inst, owner, repo, comment_id, body):
        if comment_id not in self.comments:
            raise GitHubError("no_access", "gone", 404)
        self.updated.append(comment_id)
        self.comments[comment_id] = body

    def forget_installation(self, installation_id):
        pass


def client_with(gh: FakeGitHub, ai=None, **settings):
    values = {
        "github_app_id": "1",
        "github_app_slug": "pr-summary",
        "github_app_private_key": "k",
        "github_client_id": "cid",
        "github_client_secret": "csecret",
        "github_webhook_secret": SECRET,
    }
    values.update(settings)
    return make_client(ai, github=gh, **values)


def db(c):
    return c.app.state.session_factory()


def link_installation(c, gh):
    """Sign in with email, then come back from GitHub's install screen."""
    signup(c)
    r = c.get(
        "/api/auth/github/callback",
        params={"code": "good-code", "installation_id": 42, "setup_action": "install"},
        follow_redirects=False,
    )
    assert r.headers["location"] == "/dashboard?github=connected", r.headers["location"]


def webhook(c, event: str, payload: dict, secret: str = SECRET):
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return c.post(
        "/api/github/webhook",
        content=body,
        headers={
            "X-GitHub-Event": event,
            "X-Hub-Signature-256": sig,
            "X-GitHub-Delivery": "d-1",
            "X-CSRF-Token": "",
        },  # fmt: skip
    )


def pr_payload(action="opened", sha="sha1", number=3):
    return {
        "action": action,
        "installation": {"id": 42},
        "repository": {"id": 777, "name": "secret", "owner": {"login": "Ra-vi-chilwal"}},
        "pull_request": {
            "number": number,
            "title": "Fix login",
            "head": {"sha": sha},
            "draft": False,
        },
    }


# ------------------------------------------------------------------ OAuth sign-in
def test_github_sign_in_creates_an_account_and_session():
    gh = FakeGitHub()
    c = client_with(gh)
    start = c.get("/api/auth/github/start", params={"next": "/review/5"}, follow_redirects=False)
    assert start.headers["location"].startswith("https://github.com/login/oauth/authorize")
    state = start.headers["location"].split("state=")[1]
    done = c.get(
        "/api/auth/github/callback",
        params={"code": "good-code", "state": state},
        follow_redirects=False,
    )
    assert done.headers["location"] == "/review/5"
    me = c.get("/api/auth/me").json()["user"]
    assert me["github_login"] == "ravi" and me["email"] == "ravi@example.com"


def test_sign_in_with_a_wrong_state_is_rejected():
    c = client_with(FakeGitHub())
    c.get("/api/auth/github/start", follow_redirects=False)
    r = c.get(
        "/api/auth/github/callback",
        params={"code": "good-code", "state": "forged"},
        follow_redirects=False,
    )
    assert r.headers["location"] == "/login?error=github_failed"
    assert c.get("/api/auth/me").json()["user"] is None


def test_next_parameter_cannot_redirect_off_site():
    c = client_with(FakeGitHub())
    start = c.get("/api/auth/github/start", params={"next": "//evil.com"}, follow_redirects=False)
    state = start.headers["location"].split("state=")[1]
    done = c.get(
        "/api/auth/github/callback",
        params={"code": "good-code", "state": state},
        follow_redirects=False,
    )
    assert done.headers["location"] == "/dashboard"


def test_github_account_links_to_existing_email_account_only_if_verified():
    gh = FakeGitHub(emails=[])  # GitHub gives no verified email
    c = client_with(gh)
    signup(c)
    c.post("/api/auth/logout")
    start = c.get("/api/auth/github/start", follow_redirects=False)
    state = start.headers["location"].split("state=")[1]
    c.get(
        "/api/auth/github/callback",
        params={"code": "good-code", "state": state},
        follow_redirects=False,
    )
    with db(c) as s:
        users = s.scalars(select(User).order_by(User.id)).all()
    assert len(users) == 2  # not merged into the email account
    assert users[0].github_user_id is None


# ------------------------------------------------------------------ install linking
def test_install_redirects_to_github_with_state():
    c = client_with(FakeGitHub())
    signup(c)
    r = c.get("/api/github/install", follow_redirects=False)
    assert r.headers["location"].startswith(
        "https://github.com/apps/pr-summary/installations/new?state="
    )


def test_install_is_linked_only_if_github_shows_it_to_this_user():
    gh = FakeGitHub(visible_installations={7})  # someone else's installation id
    c = client_with(gh)
    signup(c)
    r = c.get("/api/auth/github/callback", params={"code": "good-code", "installation_id": 42},
              follow_redirects=False)  # fmt: skip
    assert r.headers["location"] == "/dashboard?github=not_yours"
    assert c.get("/api/auth/me").json()["installations"] == []


def test_install_links_and_shows_in_me():
    c = client_with(FakeGitHub())
    link_installation(c, None)
    me = c.get("/api/auth/me").json()
    assert me["installations"] == [
        {
            "installation_id": 42,
            "account_login": "Ra-vi-chilwal",
            "account_type": "User",
            "repo_count": 2,
            "manage_url": "https://github.com/settings/installations/42",
        }
    ]
    with db(c) as s:
        assert [a.event for a in s.scalars(select(AuditLog))][-1] == "github_connected"


def start_link(c):
    """Click "Link it" and come back from GitHub sign-in with the matching state."""
    start = c.get("/api/github/link", follow_redirects=False)
    assert start.headers["location"].startswith("https://github.com/login/oauth/authorize")
    state = start.headers["location"].split("state=")[1]
    return c.get(
        "/api/auth/github/callback",
        params={"code": "good-code", "state": state},
        follow_redirects=False,
    )


def test_link_existing_installation_connects_it():
    # Installed on GitHub earlier, but GitHub never sent the user back (e.g. bad config).
    c = client_with(FakeGitHub())
    signup(c)
    r = start_link(c)
    assert r.headers["location"] == "/dashboard?github=connected"
    me = c.get("/api/auth/me").json()
    assert [i["installation_id"] for i in me["installations"]] == [42]
    assert me["user"]["github_login"] == "ravi"


def test_link_also_claims_an_install_the_webhook_saved_without_an_owner():
    c = client_with(FakeGitHub())
    signup(c)
    webhook(c, "installation", {"action": "created", "sender": {"id": 999},
                                "installation": {"id": 42, "account": {"login": "Ra-vi-chilwal"}}})  # fmt: skip
    with db(c) as s:
        assert s.scalar(select(GitHubInstallation)).user_id is None
    assert start_link(c).headers["location"] == "/dashboard?github=connected"
    assert len(c.get("/api/auth/me").json()["installations"]) == 1


def test_link_with_nothing_installed_says_so():
    c = client_with(FakeGitHub(visible_installations=set()))
    signup(c)
    assert start_link(c).headers["location"] == "/dashboard?github=none_found"
    assert c.get("/api/auth/me").json()["installations"] == []


def test_link_never_takes_an_installation_from_another_account():
    gh = FakeGitHub()
    c = client_with(gh)
    link_installation(c, gh)  # first account owns installation 42
    c.post("/api/auth/logout")
    gh.gh_user = {"id": 777, "login": "someone", "name": "Someone"}
    gh.emails = []
    signup(c, email="other@example.com")
    assert start_link(c).headers["location"] == "/dashboard?github=linked_elsewhere"
    assert c.get("/api/auth/me").json()["installations"] == []


def test_link_with_a_forged_state_links_nothing():
    c = client_with(FakeGitHub())
    signup(c)
    c.get("/api/github/link", follow_redirects=False)
    r = c.get("/api/auth/github/callback", params={"code": "good-code", "state": "forged"},
              follow_redirects=False)  # fmt: skip
    assert r.headers["location"] == "/login?error=github_failed"
    assert c.get("/api/auth/me").json()["installations"] == []


def test_link_failure_on_github_goes_back_to_the_dashboard():
    c = client_with(FakeGitHub())
    signup(c)
    start = c.get("/api/github/link", follow_redirects=False)
    state = start.headers["location"].split("state=")[1]
    r = c.get("/api/auth/github/callback", params={"code": "bad-code", "state": state},
              follow_redirects=False)  # fmt: skip
    assert r.headers["location"] == "/dashboard?github=link_failed"


def test_link_needs_sign_in_and_configuration():
    c = client_with(FakeGitHub())
    assert c.get("/api/github/link", follow_redirects=False).status_code == 401
    c2 = client_with(FakeGitHub(), github_client_secret=None)
    signup(c2)
    r = c2.get("/api/github/link", follow_redirects=False)
    assert r.headers["location"] == "/dashboard?github=unconfigured"


# ------------------------------------------------------------------ repos, PRs, summarize
def test_repos_prs_and_summarize_from_the_dashboard():
    c = client_with(FakeGitHub(), FakeSummarizer([ok_response(["src/app.py"])]))
    link_installation(c, None)
    repos = c.get("/api/github/repos").json()["repos"]
    assert [(r["full_name"], r["private"]) for r in repos] == [
        ("Ra-vi-chilwal/secret", True),
        ("Ra-vi-chilwal/open", False),
    ]
    pulls = c.get("/api/github/repos/Ra-vi-chilwal/secret/pulls").json()["pulls"]
    assert pulls[0]["number"] == 3
    out = c.post("/api/github/repos/Ra-vi-chilwal/secret/pulls/3/summarize").json()
    assert out["status"] == "done" and out["title"] == "Fix login" and out["diff"] == DIFF
    run = c.get(f"/api/runs/{out['run_id']}").json()["run"]
    assert run["repo"] == "Ra-vi-chilwal/secret" and run["pr_number"] == 3


def test_repo_outside_the_users_installation_is_refused():
    gh = FakeGitHub(repo_installation={"someone/else": 99})
    c = client_with(gh)
    link_installation(c, None)
    r = c.get("/api/github/repos/someone/else/pulls")
    assert r.status_code == 403
    assert "doesn't include this repository" in r.json()["detail"]


def test_private_pr_link_on_try_a_diff_uses_the_installation():
    c = client_with(FakeGitHub(), FakeSummarizer([ok_response(["src/app.py"])]))
    link_installation(c, None)
    out = c.post(
        "/api/summaries", json={"diff": "https://github.com/Ra-vi-chilwal/secret/pull/3"}
    ).json()
    assert out["status"] == "done" and out["title"] == "Fix login"


def test_uninstalled_app_while_listing_repos_is_clear():
    class Gone(FakeGitHub):
        def list_installation_repos(self, installation_id, max_pages=5):
            if max_pages == 1:
                return [], 0
            raise GitHubError(
                "uninstalled",
                "The GitHub App is no longer installed on this account. Connect GitHub again.",
            )

    c = client_with(Gone())
    link_installation(c, None)
    r = c.get("/api/github/repos")
    assert r.status_code == 409 and "Connect GitHub again" in r.json()["detail"]
    assert c.get("/api/auth/me").json()["installations"] == []


# ------------------------------------------------------------------ webhooks
def test_webhook_rejects_bad_signatures_and_needs_no_csrf():
    c = client_with(FakeGitHub())
    assert webhook(c, "ping", {"zen": "hi"}, secret="wrong").status_code == 401
    assert webhook(c, "ping", {"zen": "hi"}).status_code == 200


def test_installation_created_and_deleted_events():
    gh = FakeGitHub()
    c = client_with(gh)
    signup(c)
    payload = {
        "action": "created",
        "installation": {"id": 42, "account": {"login": "Ra-vi-chilwal", "type": "User", "id": 9},
                         "repository_selection": "selected"},
        "repositories": [{"id": 1}, {"id": 2}, {"id": 3}],
        "sender": {"id": 501},
    }  # fmt: skip
    assert webhook(c, "installation", payload).status_code == 200
    with db(c) as s:
        inst = s.scalar(select(GitHubInstallation))
        assert inst.repo_count == 3 and inst.deleted_at is None
    webhook(c, "installation_repositories", {"installation": {"id": 42}, "repositories_added": [{"id": 4}],
                                             "repositories_removed": []})  # fmt: skip
    with db(c) as s:
        assert s.scalar(select(GitHubInstallation)).repo_count == 4
    webhook(c, "installation", {"action": "deleted", "installation": {"id": 42}})
    with db(c) as s:
        assert s.scalar(select(GitHubInstallation)).deleted_at is not None
        events = [a.event for a in s.scalars(select(AuditLog))]
    assert events[-3:] == ["github_connected", "github_repos_changed", "github_disconnected"]


def test_pr_opened_posts_one_comment_and_synchronize_edits_it():
    gh = FakeGitHub()
    ai = FakeSummarizer([ok_response(["src/app.py"]), ok_response(["src/app.py"])])
    c = client_with(gh, ai)
    link_installation(c, gh)

    assert webhook(c, "pull_request", pr_payload("opened", "sha1")).status_code == 202
    assert gh.created == [1000] and gh.updated == []
    assert gh.comments[1000].endswith("Written by AI. It can be wrong.")

    webhook(c, "pull_request", pr_payload("synchronize", "sha2"))
    assert gh.created == [1000] and gh.updated == [1000]  # same comment, edited
    assert len(ai.calls) == 2
    with db(c) as s:
        assert s.scalar(select(PRComment)).comment_id == 1000
        events = [
            a.event for a in s.scalars(select(AuditLog).where(AuditLog.event == "summary_posted"))
        ]
    assert events == ["summary_posted", "summary_posted"]


def test_same_commit_twice_makes_no_second_ai_call():
    gh = FakeGitHub()
    ai = FakeSummarizer([ok_response(["src/app.py"])])
    c = client_with(gh, ai)
    webhook(c, "pull_request", pr_payload("opened", "sha1"))
    webhook(c, "pull_request", pr_payload("reopened", "sha1"))
    assert len(ai.calls) == 1 and gh.created == [1000]


def test_if_the_diff_cant_be_read_nothing_is_posted():
    gh = FakeGitHub(
        fail_diff=GitHubError(
            "too_large", "This pull request is too large for GitHub to send as a diff."
        )
    )
    ai = FakeSummarizer()
    c = client_with(gh, ai)
    webhook(c, "pull_request", pr_payload())
    assert gh.created == [] and ai.calls == []
    with db(c) as s:
        run = s.scalar(select(Run))
    assert run.status == "failed" and run.message.startswith("Failed, nothing posted.")


def test_if_the_ai_fails_nothing_is_posted():
    from tests.helpers import retryable_error

    gh = FakeGitHub()
    c = client_with(gh, FakeSummarizer([retryable_error(), retryable_error()]))
    webhook(c, "pull_request", pr_payload())
    assert gh.created == []


def test_lockfile_only_pr_posts_nothing():
    gh = FakeGitHub(diff=make_diff("package-lock.json"))
    ai = FakeSummarizer()
    c = client_with(gh, ai)
    webhook(c, "pull_request", pr_payload())
    assert gh.created == [] and ai.calls == []


def test_monthly_repo_cap_stops_before_the_ai():
    gh = FakeGitHub()
    ai = FakeSummarizer([ok_response(["src/app.py"])])
    c = client_with(gh, ai, reviews_per_repo_per_month=1)
    webhook(c, "pull_request", pr_payload("opened", "sha1"))
    webhook(c, "pull_request", pr_payload("synchronize", "sha2"))
    assert len(ai.calls) == 1
    with db(c) as s:
        assert s.scalars(select(Run.status).order_by(Run.id)).all() == ["done", "capped"]


def test_posting_failure_marks_the_run_failed():
    gh = FakeGitHub(
        fail_post=GitHubError(
            "rate_limited", "GitHub's rate limit was reached. Try again in a few minutes."
        )
    )
    c = client_with(gh, FakeSummarizer([ok_response(["src/app.py"])]))
    webhook(c, "pull_request", pr_payload())
    with db(c) as s:
        run = s.scalar(select(Run))
        assert run.status == "failed" and "rate limit" in run.message
        assert "summary_post_failed" in [a.event for a in s.scalars(select(AuditLog))]


def test_draft_prs_are_skipped():
    gh = FakeGitHub()
    c = client_with(gh, FakeSummarizer())
    payload = pr_payload()
    payload["pull_request"]["draft"] = True
    assert webhook(c, "pull_request", payload).json()["skipped"] == "draft"
    assert gh.created == []


def test_on_vercel_the_webhook_finishes_its_work_before_answering(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    gh = FakeGitHub()
    c = client_with(gh, FakeSummarizer([ok_response(["src/app.py"])]))
    r = webhook(c, "pull_request", pr_payload())
    assert r.status_code == 200 and r.json()["result"] == "posted"
    assert gh.created == [1000]

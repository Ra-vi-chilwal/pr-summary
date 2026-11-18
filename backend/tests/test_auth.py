"""Signup, login, logout, sessions, CSRF, rate limits, protected routes, audit log."""

from sqlalchemy import select

from app.models import AuditLog, AuthSession, User
from app.security import (
    SESSION_COOKIE,
    hash_password,
    password_problem,
    token_hash,
    verify_password,
)
from tests.helpers import GOOD_PASSWORD, FakeSummarizer, make_client, make_diff, ok_response, signup


def db(client):
    return client.app.state.session_factory()


def audit_events(client) -> list[str]:
    with db(client) as s:
        return [a.event for a in s.scalars(select(AuditLog).order_by(AuditLog.id))]


# ------------------------------------------------------------------ passwords
def test_passwords_are_hashed_with_argon2_and_verified():
    h = hash_password(GOOD_PASSWORD)
    assert h.startswith("$argon2id$") and GOOD_PASSWORD not in h
    assert verify_password(h, GOOD_PASSWORD)
    assert not verify_password(h, "wrong password!!")
    assert not verify_password(None, GOOD_PASSWORD)  # GitHub-only accounts have no password
    assert not verify_password("not-a-hash", GOOD_PASSWORD)


def test_password_rules():
    assert password_problem("short") == "Use at least 10 characters."
    assert password_problem("password123") is not None
    assert password_problem("aaaaaaaaaaaa") is not None
    assert password_problem("ravi@example.com", "ravi@example.com") is not None
    assert password_problem(GOOD_PASSWORD) is None


# ------------------------------------------------------------------ signup
def test_signup_creates_user_session_and_audit():
    c = make_client()
    user = signup(c, email="Ravi@Example.com ")
    assert user["email"] == "ravi@example.com" and user["name"] == "Ravi"
    assert c.get("/api/auth/me").json()["user"]["id"] == user["id"]
    with db(c) as s:
        stored = s.scalar(select(User))
        assert stored.password_hash.startswith("$argon2id$")
        session_row = s.scalar(select(AuthSession))
        # Only the hash of the cookie token is stored.
        assert session_row.token_hash == token_hash(c.cookies[SESSION_COOKIE])
    assert audit_events(c) == ["signup"]


def test_session_cookie_is_httponly_lax_and_secure_in_production():
    c = make_client(cookie_secure=True)
    # The http:// test client drops Secure cookies, so supply the CSRF pair by hand.
    c.cookies.set("prs_csrf", "t")
    c.headers["X-CSRF-Token"] = "t"
    r = c.post("/api/auth/signup", json={"name": "R", "email": "r@x.io", "password": GOOD_PASSWORD})
    cookie = next(h for h in r.headers.get_list("set-cookie") if h.startswith(SESSION_COOKIE))
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Secure" in cookie


def test_signup_validation_messages_per_field():
    c = make_client()
    r = c.post("/api/auth/signup", json={"name": " ", "email": "nope", "password": "short"})
    assert r.status_code == 422
    assert r.json()["fields"] == {
        "name": "Tell us what to call you.",
        "email": "Enter an email address like name@example.com.",
        "password": "Use at least 10 characters.",
    }


def test_duplicate_email_has_a_clear_message():
    c = make_client()
    signup(c)
    r = make_client_with_same_db(c).post(
        "/api/auth/signup",
        json={"name": "X", "email": "RAVI@example.com", "password": GOOD_PASSWORD},
    )
    assert r.status_code == 409
    assert (
        r.json()["fields"]["email"] == "That email is already registered. Try signing in instead."
    )


def make_client_with_same_db(c):
    """A second browser on the same app."""
    from fastapi.testclient import TestClient

    other = TestClient(c.app)
    other.get("/api/health")
    other.headers["X-CSRF-Token"] = other.cookies.get("prs_csrf", "")
    return other


# ------------------------------------------------------------------ login / logout
def test_login_success_and_failure_are_audited():
    c = make_client()
    signup(c)
    c.post("/api/auth/logout")
    bad = c.post(
        "/api/auth/login", json={"email": "ravi@example.com", "password": "wrong password!!"}
    )
    assert bad.status_code == 401
    assert bad.json()["detail"] == "Email or password is incorrect."
    unknown = c.post(
        "/api/auth/login", json={"email": "who@example.com", "password": GOOD_PASSWORD}
    )
    assert unknown.json()["detail"] == "Email or password is incorrect."  # no account enumeration
    ok = c.post("/api/auth/login", json={"email": "RAVI@example.com", "password": GOOD_PASSWORD})
    assert ok.status_code == 200 and ok.json()["user"]["email"] == "ravi@example.com"
    assert audit_events(c) == ["signup", "logout", "login_failed", "login_failed", "login"]
    with db(c) as s:
        failed = s.scalars(select(AuditLog).where(AuditLog.event == "login_failed")).all()
        assert failed[0].detail == {"email": "r***@example.com"}  # masked, never the password


def test_logout_ends_the_session():
    c = make_client()
    signup(c)
    token = c.cookies[SESSION_COOKIE]
    assert c.post("/api/auth/logout").status_code == 204
    assert c.get("/api/auth/me").json()["user"] is None
    with db(c) as s:
        assert (
            s.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(token))) is None
        )


def test_too_many_failed_logins_for_one_email_are_blocked():
    c = make_client(auth_rate_limit=100)
    signup(c)
    c.post("/api/auth/logout")
    for _ in range(5):
        c.post(
            "/api/auth/login", json={"email": "ravi@example.com", "password": "wrong password!!"}
        )
    r = c.post("/api/auth/login", json={"email": "ravi@example.com", "password": GOOD_PASSWORD})
    assert r.status_code == 429
    assert "Too many failed attempts" in r.json()["detail"]
    assert "login_blocked" in audit_events(c)


def test_login_and_signup_are_rate_limited_per_ip():
    c = make_client(auth_rate_limit=3)
    for _ in range(3):
        c.post("/api/auth/login", json={"email": "a@b.co", "password": "whatever-123"})
    r = c.post("/api/auth/login", json={"email": "a@b.co", "password": "whatever-123"})
    assert r.status_code == 429
    assert r.json()["detail"] == "Too many attempts. Wait a few minutes and try again."


# ------------------------------------------------------------------ CSRF & protection
def test_state_changing_requests_need_the_csrf_token():
    c = make_client()
    c.headers.pop("X-CSRF-Token")
    r = c.post("/api/auth/signup", json={"name": "R", "email": "r@x.io", "password": GOOD_PASSWORD})
    assert r.status_code == 403
    assert r.json()["detail"] == "Your session expired. Reload the page and try again."
    c.headers["X-CSRF-Token"] = "not-the-cookie"
    assert c.post("/api/auth/logout").status_code == 403


def test_protected_routes_need_sign_in_but_try_a_diff_is_public():
    c = make_client(FakeSummarizer())
    assert c.get("/api/runs").status_code == 401
    assert c.get("/api/runs/1").status_code == 401
    assert c.get("/api/github/repos").status_code == 401
    assert c.get("/api/runs").json()["detail"] == "Please sign in to continue."
    assert c.post("/api/summaries", json={"diff": make_diff("a.py")}).status_code == 200


def test_runs_are_private_to_their_owner():
    c = make_client(FakeSummarizer([ok_response(["src/app.py"])]))
    signup(c)
    run_id = c.post("/api/summaries", json={"diff": make_diff("src/app.py")}).json()["run_id"]
    other = make_client_with_same_db(c)
    signup(other, email="someone@else.io")
    assert other.get(f"/api/runs/{run_id}").status_code == 404
    assert other.get("/api/runs").json()["runs"] == []


def test_only_the_same_browser_can_claim_an_anonymous_run():
    c = make_client(FakeSummarizer([ok_response(["src/app.py"])] * 2))
    run_id = c.post("/api/summaries", json={"diff": make_diff("src/app.py")}).json()["run_id"]

    stranger = make_client_with_same_db(c)
    signup(stranger, email="stranger@x.io")
    assert stranger.get(f"/api/runs/{run_id}").status_code == 404  # can't guess ids

    signup(c)  # the same browser signs up afterwards
    assert c.get(f"/api/runs/{run_id}").status_code == 200
    assert [r["id"] for r in c.get("/api/runs").json()["runs"]] == [run_id]


def test_request_id_is_returned_and_accepted():
    c = make_client()
    r = c.get("/api/health", headers={"X-Request-ID": "abc-123"})
    assert r.headers["X-Request-ID"] == "abc-123"
    r = c.get("/api/health", headers={"X-Request-ID": "bad id with spaces"})
    assert (
        r.headers["X-Request-ID"] != "bad id with spaces" and len(r.headers["X-Request-ID"]) == 32
    )


def test_me_reports_configuration_without_secrets():
    c = make_client(github_app_id="1", github_app_slug="pr-summary", github_app_private_key="x")
    me = c.get("/api/auth/me").json()
    assert me == {
        "user": None,
        "installations": [],
        "github_app_configured": True,
        "github_login_configured": False,
    }

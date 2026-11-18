"""GitHub client: app JWT, cached installation tokens, error mapping, webhook signatures."""

import hashlib
import hmac
import json
import time

import httpx2
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import Settings
from app.github_app import GitHub, GitHubError, verify_webhook_signature

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PEM = _KEY.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
).decode()
PUBLIC = _KEY.public_key()


def settings(**kw) -> Settings:
    base = {
        "github_app_id": "12345",
        "github_app_slug": "pr-summary",
        # .env files usually hold the key on one line with \n escapes
        "github_app_private_key": PEM.replace("\n", "\\n"),
        "_env_file": None,
    }
    base.update(kw)
    return Settings(**base)


def gh(handler) -> GitHub:
    return GitHub(settings(), http=httpx2.Client(transport=httpx2.MockTransport(handler)))


# ------------------------------------------------------------------ webhook signatures
def sig(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_valid_signature_is_accepted():
    body = b'{"action":"opened"}'
    assert verify_webhook_signature("s3cret", body, sig("s3cret", body))


@pytest.mark.parametrize(
    ("secret", "header"),
    [
        ("s3cret", None),  # missing header
        ("s3cret", "sha1=abc"),  # wrong scheme
        ("s3cret", sig("other", b'{"action":"opened"}')),  # wrong secret
        ("s3cret", sig("s3cret", b'{"action":"closed"}')),  # body was changed
        (None, sig("s3cret", b'{"action":"opened"}')),  # we have no secret configured
    ],
)
def test_invalid_signatures_are_rejected(secret, header):
    assert not verify_webhook_signature(secret, b'{"action":"opened"}', header)


# ------------------------------------------------------------------ app JWT & tokens
def test_app_jwt_is_rs256_signed_and_short_lived():
    token = gh(lambda r: httpx2.Response(500)).app_jwt(now=1_000_000)
    claims = jwt.decode(token, PUBLIC, algorithms=["RS256"], options={"verify_exp": False})
    assert claims == {"iat": 999_940, "exp": 1_000_540, "iss": "12345"}


def test_installation_tokens_are_cached_until_near_expiry():
    calls = []

    def handler(req):
        calls.append(req.url.path)
        assert req.headers["Authorization"].startswith("Bearer ey")  # the app JWT
        expires = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 3600))
        return httpx2.Response(201, json={"token": f"ghs_{len(calls)}", "expires_at": expires})

    client = gh(handler)
    assert client.installation_token(7) == "ghs_1"
    assert client.installation_token(7) == "ghs_1"
    assert calls == ["/app/installations/7/access_tokens"]
    client.forget_installation(7)
    assert client.installation_token(7) == "ghs_2"


def test_almost_expired_tokens_are_refreshed():
    n = {"i": 0}

    def handler(req):
        n["i"] += 1
        soon = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 30))
        return httpx2.Response(201, json={"token": f"ghs_{n['i']}", "expires_at": soon})

    client = gh(handler)
    client.installation_token(7)
    assert client.installation_token(7) == "ghs_2"


def test_unconfigured_app_says_so():
    client = GitHub(
        Settings(_env_file=None), http=httpx2.Client(transport=httpx2.MockTransport(lambda r: None))
    )
    with pytest.raises(GitHubError, match="isn't configured"):
        client.app_jwt()


# ------------------------------------------------------------------ error mapping
def token_then(status: int, headers: dict | None = None, path_contains: str = "/pulls"):
    def handler(req):
        if req.url.path.endswith("/access_tokens"):
            return httpx2.Response(
                201, json={"token": "ghs_x", "expires_at": "2999-01-01T00:00:00Z"}
            )
        return httpx2.Response(status, headers=headers or {}, json={"message": "x"})

    return gh(handler)


def test_uninstalled_app_is_reported_clearly():
    client = gh(lambda r: httpx2.Response(404, json={"message": "Not Found"}))
    with pytest.raises(GitHubError) as e:
        client.installation_token(99)
    assert e.value.kind == "uninstalled"
    assert "no longer installed" in e.value.message


def test_revoked_repo_access_is_reported_clearly():
    with pytest.raises(GitHubError) as e:
        token_then(404).list_open_pulls(1, "o", "r")
    assert e.value.kind == "no_access"


def test_rate_limit_is_reported_with_wait_time():
    reset = str(int(time.time()) + 600)
    with pytest.raises(GitHubError) as e:
        token_then(403, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": reset}).list_open_pulls(
            1, "o", "r"
        )
    assert e.value.kind == "rate_limited"
    assert "about 10 min" in e.value.message


def test_too_large_diff_is_reported_clearly():
    with pytest.raises(GitHubError) as e:
        token_then(406).get_pull_diff(1, "o", "r", 5)
    assert e.value.kind == "too_large"


def test_network_errors_are_safe():
    def handler(req):
        raise httpx2.ConnectError("down")

    with pytest.raises(GitHubError) as e:
        gh(handler).get_installation(1)
    assert e.value.kind == "unavailable"


def test_diff_is_requested_with_the_diff_media_type():
    seen = {}

    def handler(req):
        if req.url.path.endswith("/access_tokens"):
            return httpx2.Response(
                201, json={"token": "ghs_x", "expires_at": "2999-01-01T00:00:00Z"}
            )
        seen["accept"] = req.headers["Accept"]
        seen["auth"] = req.headers["Authorization"]
        return httpx2.Response(200, text="diff --git a/x b/x\n")

    assert gh(handler).get_pull_diff(1, "o", "r", 5).startswith("diff --git")
    assert seen == {"accept": "application/vnd.github.diff", "auth": "Bearer ghs_x"}


def test_github_calls_are_logged_without_tokens(capsys):
    from app.logging_setup import configure_logging

    configure_logging("INFO")

    def handler(req):
        if req.url.path.endswith("/access_tokens"):
            return httpx2.Response(
                201, json={"token": "ghs_" + "s" * 36, "expires_at": "2999-01-01T00:00:00Z"}
            )
        return httpx2.Response(200, headers={"x-ratelimit-remaining": "4999"}, json=[])

    gh(handler).list_open_pulls(1, "o", "r")
    lines = [json.loads(x) for x in capsys.readouterr().out.strip().splitlines()]
    calls = [x for x in lines if x["event"] == "github_call"]
    assert calls[-1]["endpoint"] == "GET /repos/{owner}/{repo}/pulls"
    assert calls[-1]["status"] == 200 and calls[-1]["rate_limit_remaining"] == 4999
    assert "ghs_" not in json.dumps(lines)

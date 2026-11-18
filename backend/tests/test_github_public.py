import httpx2
import pytest

from app.github_public import PRFetchError, PRLink, fetch_public_pr, parse_pr_link
from tests.helpers import FakeSummarizer, make_client, make_diff, ok_response, signup

LINK = PRLink("Ra-vi-chilwal", "trustRush-fastAPI", 1)


@pytest.mark.parametrize(
    "text",
    [
        "https://github.com/Ra-vi-chilwal/trustRush-fastAPI/pull/1",
        "  https://github.com/Ra-vi-chilwal/trustRush-fastAPI/pull/1/files  ",
        "https://github.com/Ra-vi-chilwal/trustRush-fastAPI/pull/1.diff",
        "https://patch-diff.githubusercontent.com/raw/Ra-vi-chilwal/trustRush-fastAPI/pull/1.diff",
    ],
)
def test_parse_pr_link_variants(text):
    assert parse_pr_link(text) == LINK


@pytest.mark.parametrize(
    "text",
    [
        "diff --git a/x b/x",
        "https://example.com/a/b/pull/1",
        "https://github.com/a/b/issues/1",
        "see https://github.com/a/b/pull/1 for context\ndiff --git a/x b/x",
    ],
)
def test_parse_pr_link_rejects_non_links(text):
    assert parse_pr_link(text) is None


def mock_client(handler) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(handler), follow_redirects=True)


def test_fetch_returns_diff_and_title():
    def handler(req):
        if req.url.host == "api.github.com":
            return httpx2.Response(200, json={"title": "chnage in the branch"})
        assert str(req.url) == LINK.diff_url
        return httpx2.Response(200, text="diff --git a/a.py b/a.py\n")

    diff, title = fetch_public_pr(LINK, client=mock_client(handler))
    assert diff.startswith("diff --git")
    assert title == "chnage in the branch"


def test_fetch_title_failure_is_ignored():
    def handler(req):
        if req.url.host == "api.github.com":
            return httpx2.Response(403, json={"message": "rate limit"})
        return httpx2.Response(200, text="diff --git a/a.py b/a.py\n")

    assert fetch_public_pr(LINK, client=mock_client(handler))[1] == ""


def test_private_or_missing_pr_gives_clear_message():
    client = mock_client(lambda req: httpx2.Response(404))
    with pytest.raises(PRFetchError, match="private"):
        fetch_public_pr(LINK, client=client)


def test_network_error_gives_safe_message():
    def handler(req):
        raise httpx2.ConnectError("down")

    with pytest.raises(PRFetchError, match="Couldn't reach GitHub"):
        fetch_public_pr(LINK, client=mock_client(handler))


def app_client(fetcher, ai=None):
    return make_client(ai, pr_fetcher=fetcher)


def test_api_summarizes_a_pasted_pr_link():
    seen = []

    def fetcher(link):
        seen.append(link)
        return make_diff("src/app.py"), "chnage in the branch"

    c = app_client(fetcher, FakeSummarizer([ok_response(["src/app.py"])]))
    signup(c)
    body = c.post("/api/summaries", json={"diff": LINK.diff_url, "title": ""}).json()
    assert seen == [LINK]
    assert body["status"] == "done"
    assert body["title"] == "chnage in the branch"
    assert body["diff"].startswith("diff --git")  # back to the browser for the Review screen
    run = c.get(f"/api/runs/{body['run_id']}").json()
    assert run["run"]["title"] == "chnage in the branch"


def test_api_pasted_diff_is_not_echoed_back():
    c = app_client(lambda link: pytest.fail("should not fetch"), FakeSummarizer())
    body = c.post("/api/summaries", json={"diff": make_diff("src/app.py")}).json()
    assert body["diff"] is None


def test_api_fetch_failure_returns_message_and_creates_no_run():
    def fetcher(link):
        raise PRFetchError("Couldn't read this PR. Nothing was sent to the AI.")

    c = app_client(fetcher)
    signup(c)
    r = c.post("/api/summaries", json={"diff": "https://github.com/a/b/pull/9"})
    assert r.status_code == 422
    assert r.json()["detail"] == "Couldn't read this PR. Nothing was sent to the AI."
    assert c.get("/api/runs").json()["runs"] == []

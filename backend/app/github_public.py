"""Fetch a PUBLIC pull request's diff from a link (dev "Try a diff" only).

Private repos need the GitHub App (later step). The diff is only held in memory for the
summary and returned to the user's own browser; it is never stored.
"""

import re
from dataclasses import dataclass

import httpx2

# github.com/<owner>/<repo>/pull/<n>[/files|.diff|...] or the raw patch-diff redirect target.
_PR_LINK = re.compile(
    r"^https?://(?:www\.)?(?:github\.com|patch-diff\.githubusercontent\.com/raw)"
    r"/([\w.-]+)/([\w.-]+)/pull/(\d+)(?:[/.?#]\S*)?$"
)
MAX_DIFF_BYTES = 2_000_000


@dataclass(frozen=True)
class PRLink:
    owner: str
    repo: str
    number: int

    @property
    def diff_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}/pull/{self.number}.diff"

    @property
    def api_url(self) -> str:
        return f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls/{self.number}"


class PRFetchError(Exception):
    """message is safe to show the user."""


def parse_pr_link(text: str) -> PRLink | None:
    """A PR link pasted on its own (not a diff that happens to contain a URL)."""
    match = _PR_LINK.match(text.strip())
    if not match:
        return None
    return PRLink(match.group(1), match.group(2), int(match.group(3)))


def fetch_public_pr(link: PRLink, client: httpx2.Client | None = None) -> tuple[str, str]:
    """Returns (diff_text, pr_title). Title is "" if it can't be read."""
    own_client = client is None
    client = client or httpx2.Client(
        follow_redirects=True, timeout=20, headers={"User-Agent": "pr-summary-dev"}
    )
    try:
        try:
            resp = client.get(link.diff_url)
        except httpx2.HTTPError as e:
            raise PRFetchError("Couldn't reach GitHub. Nothing was sent to the AI.") from e
        if resp.status_code == 404:
            raise PRFetchError(
                "Couldn't read this PR. The link may be wrong, or the repo is private "
                "(private repos need the GitHub App, coming next). Nothing was sent to the AI."
            )
        if resp.status_code != 200:
            raise PRFetchError("GitHub didn't return the diff. Nothing was sent to the AI.")
        if len(resp.content) > MAX_DIFF_BYTES:
            raise PRFetchError("This PR's diff is too big to summarize, so we skipped it.")

        title = ""
        try:
            meta = client.get(link.api_url, headers={"Accept": "application/vnd.github+json"})
            if meta.status_code == 200:
                title = str(meta.json().get("title") or "")
        except (httpx2.HTTPError, ValueError):
            pass  # the title is nice to have; the diff is what matters
        return resp.text, title
    finally:
        if own_client:
            client.close()

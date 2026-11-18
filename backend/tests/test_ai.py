"""ClaudeSummarizer against a fake Anthropic client (no network, no key)."""

import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.ai import MODEL, AIError, ClaudeSummarizer, cost_microusd

GOOD = {
    "overview": "Adds retry.",
    "files": [{"path": "a.py", "note": "Retry loop.", "unsure": False}],
    "check_first": [{"path": "a.py", "reason": "Could double-charge."}],
}


class FakeMessages:
    def __init__(self, result):
        self.result = result
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def fake_client(result):
    messages = FakeMessages(result)
    return SimpleNamespace(beta=SimpleNamespace(messages=messages)), messages


def response(text: str | None, stop_reason="end_turn"):
    content = [SimpleNamespace(type="text", text=text)] if text is not None else []
    return SimpleNamespace(
        model=MODEL,
        stop_reason=stop_reason,
        content=content,
        usage=SimpleNamespace(input_tokens=1200, output_tokens=300),
    )


def http_error(cls, status):
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("err", response=httpx.Response(status, request=req), body=None)


def test_parses_structured_output_and_sends_expected_request():
    client, messages = fake_client(response(json.dumps(GOOD)))
    out = ClaudeSummarizer("k", client=client).summarize("sys", "user")
    assert out.result.check_first[0].reason == "Could double-charge."
    assert (out.usage.input_tokens, out.usage.output_tokens) == (1200, 300)
    k = messages.kwargs
    assert k["model"] == "claude-opus-5-5"
    assert k["output_config"]["format"]["type"] == "json_schema"
    assert k["output_config"]["effort"] == "high"
    assert k["fallbacks"] == "default"
    assert k["messages"] == [{"role": "user", "content": "user"}]


@pytest.mark.parametrize(
    ("raised", "kind", "retryable"),
    [
        (http_error(anthropic.RateLimitError, 429), "rate_limited", True),
        (http_error(anthropic.InternalServerError, 529), "http_529", True),
        (http_error(anthropic.AuthenticationError, 401), "http_401", False),
        (anthropic.APIConnectionError(request=httpx.Request("POST", "https://x")),
         "connection", True),
    ],
)  # fmt: skip
def test_api_errors_are_classified(raised, kind, retryable):
    client, _ = fake_client(raised)
    with pytest.raises(AIError) as e:
        ClaudeSummarizer("k", client=client).summarize("s", "u")
    assert (e.value.kind, e.value.retryable) == (kind, retryable)


@pytest.mark.parametrize(
    ("resp", "kind", "retryable"),
    [
        (response(None, stop_reason="refusal"), "refusal", False),
        (response("{", stop_reason="max_tokens"), "max_tokens", False),
        (response("not json"), "bad_output", True),
        (response(None), "no_text", True),
    ],
)
def test_bad_responses_fail_with_usage(resp, kind, retryable):
    client, _ = fake_client(resp)
    with pytest.raises(AIError) as e:
        ClaudeSummarizer("k", client=client).summarize("s", "u")
    assert (e.value.kind, e.value.retryable) == (kind, retryable)
    assert e.value.usage.input_tokens == 1200


def test_cost():
    assert cost_microusd("claude-opus-5-5", 1_000_000, 0) == 4_000_000
    assert cost_microusd("claude-opus-5-5", 0, 1_000_000) == 20_000_000
    assert cost_microusd("some-other-model", 1_000_000, 0) == 10_000_000

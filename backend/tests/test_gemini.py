"""GeminiSummarizer against a fake google-genai client (no network, no key)."""

import json
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors as genai_errors

from app.ai import (
    AIError,
    ClaudeSummarizer,
    GeminiSummarizer,
    cost_microusd,
    make_summarizer,
)

GOOD = {
    "overview": "Adds retry.",
    "files": [{"path": "a.py", "note": "Retry loop.", "unsure": False}],
    "check_first": [{"path": "a.py", "reason": "Could double-charge."}],
}


class FakeModels:
    def __init__(self, result):
        self.result = result
        self.kwargs = None

    def generate_content(self, **kwargs):
        self.kwargs = kwargs
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def fake_client(result):
    models = FakeModels(result)
    return SimpleNamespace(models=models), models


def response(text, finish="STOP", thoughts=50):
    return SimpleNamespace(
        text=text,
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name=finish))],
        usage_metadata=SimpleNamespace(
            prompt_token_count=1000, candidates_token_count=200, thoughts_token_count=thoughts
        ),
    )


def gemini(result):
    client, models = fake_client(result)
    return GeminiSummarizer("k", client=client), models


def test_parses_json_and_sends_schema():
    s, models = gemini(response(json.dumps(GOOD)))
    out = s.summarize("sys", "user")
    assert out.result.check_first[0].path == "a.py"
    assert out.usage.model == "gemini-3.8-flash"
    assert (out.usage.input_tokens, out.usage.output_tokens) == (1000, 250)  # thoughts count
    k = models.kwargs
    assert k["model"] == "gemini-3.8-flash"
    assert k["contents"] == "user"
    assert k["config"].system_instruction == "sys"
    assert k["config"].response_mime_type == "application/json"
    assert k["config"].response_json_schema["required"] == ["overview", "files", "check_first"]


@pytest.mark.parametrize(
    ("raised", "kind", "retryable"),
    [
        (genai_errors.ClientError(429, {"error": {"message": "quota"}}), "http_429", True),
        (genai_errors.ClientError(400, {"error": {"message": "bad"}}), "http_400", False),
        (genai_errors.ClientError(403, {"error": {"message": "key"}}), "http_403", False),
        (genai_errors.ServerError(503, {"error": {"message": "busy"}}), "http_503", True),
        (httpx.ConnectError("down"), "connection", True),
    ],
)
def test_errors_are_classified(raised, kind, retryable):
    s, _ = gemini(raised)
    with pytest.raises(AIError) as e:
        s.summarize("s", "u")
    assert (e.value.kind, e.value.retryable) == (kind, retryable)


@pytest.mark.parametrize(
    ("resp", "kind", "retryable"),
    [
        (response("{", finish="MAX_TOKENS"), "max_tokens", False),
        (response(None, finish="SAFETY"), "refusal", False),
        (response("not json"), "bad_output", True),
        (response(None), "no_text", True),
    ],
)
def test_bad_responses_fail_with_usage(resp, kind, retryable):
    s, _ = gemini(resp)
    with pytest.raises(AIError) as e:
        s.summarize("s", "u")
    assert (e.value.kind, e.value.retryable) == (kind, retryable)
    assert e.value.usage.input_tokens == 1000


def test_gemini_cost_uses_paid_price():
    assert cost_microusd("gemini-3.8-flash", 1_000_000, 1_000_000) == 750_000 + 3_750_000


def test_make_summarizer_picks_provider():
    assert isinstance(make_summarizer("gemini", None, "g"), GeminiSummarizer)
    assert isinstance(make_summarizer("claude", "a", None), ClaudeSummarizer)
    assert make_summarizer("gemini", "a", None) is None  # no Gemini key -> runs fail safely
    with pytest.raises(ValueError):
        make_summarizer("openai", "a", "g")

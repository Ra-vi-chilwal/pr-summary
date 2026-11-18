"""The only place we call an AI. Only the filtered diff is sent; nothing is stored.

Two providers, picked by the AI_PROVIDER setting: Claude (Anthropic) or Gemini (Google).
"""

from dataclasses import dataclass
from typing import Protocol

import anthropic
import httpx2
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import ValidationError

from app.schema import SUMMARY_JSON_SCHEMA, SummaryResult

MODEL = "claude-opus-5-5"
GEMINI_MODEL = "gemini-3.8-flash"

# USD per 1M tokens (input, output). Unknown models (e.g. a fallback) are priced high
# on purpose so the spend cap errs on the safe side. Gemini is counted at its paid price
# even on the free tier, so the $10 cap still means something if billing is turned on.
PRICES_PER_MTOK = {"claude-opus-5-5": (4.0, 20.0), "gemini-3.8-flash": (0.75, 3.75)}
UNKNOWN_MODEL_PRICE = (10.0, 50.0)


def cost_microusd(model: str, input_tokens: int, output_tokens: int) -> int:
    price_in, price_out = PRICES_PER_MTOK.get(model, UNKNOWN_MODEL_PRICE)
    # $X per 1M tokens == X micro-dollars per token.
    return round(input_tokens * price_in + output_tokens * price_out)


@dataclass
class TokenUsage:
    model: str
    input_tokens: int
    output_tokens: int


@dataclass
class AIResponse:
    result: SummaryResult
    usage: TokenUsage


class AIError(Exception):
    def __init__(self, kind: str, retryable: bool, usage: TokenUsage | None = None):
        super().__init__(kind)
        self.kind = kind
        self.retryable = retryable
        self.usage = usage


class Summarizer(Protocol):
    def summarize(self, system: str, user: str) -> AIResponse: ...


class ClaudeSummarizer:
    def __init__(self, api_key: str, client: anthropic.Anthropic | None = None):
        # Retries are handled by the caller (exactly one), so the SDK must not retry.
        self.client = client or anthropic.Anthropic(api_key=api_key, max_retries=0, timeout=300)

    def summarize(self, system: str, user: str) -> AIResponse:
        try:
            response = self.client.beta.messages.create(
                model=MODEL,
                max_tokens=16000,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={
                    "effort": "high",
                    "format": {"type": "json_schema", "schema": SUMMARY_JSON_SCHEMA},
                },
            )
        except anthropic.RateLimitError as e:
            raise AIError("rate_limited", retryable=True) from e
        except anthropic.APIStatusError as e:
            raise AIError(f"http_{e.status_code}", retryable=e.status_code >= 500) from e
        except anthropic.APIConnectionError as e:
            raise AIError("connection", retryable=True) from e

        usage = TokenUsage(
            model=response.model or MODEL,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        if response.stop_reason == "refusal":
            raise AIError("refusal", retryable=False, usage=usage)
        if response.stop_reason == "max_tokens":
            raise AIError("max_tokens", retryable=False, usage=usage)

        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise AIError("no_text", retryable=True, usage=usage)
        try:
            result = SummaryResult.model_validate_json(text)
        except ValidationError as e:
            raise AIError("bad_output", retryable=True, usage=usage) from e
        return AIResponse(result=result, usage=usage)


class GeminiSummarizer:
    """Google Gemini with JSON-schema structured output.

    Free-tier note: Google may use free-tier content to improve its products. Use the free
    tier only on your own repos; use a paid key (or Claude) before outside users.
    """

    def __init__(self, api_key: str, model: str = GEMINI_MODEL, client: genai.Client | None = None):
        self.model = model
        self.client = client or genai.Client(api_key=api_key)

    def summarize(self, system: str, user: str) -> AIResponse:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=user,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_json_schema=SUMMARY_JSON_SCHEMA,
                    max_output_tokens=16000,
                ),
            )
        except genai_errors.ClientError as e:  # 4xx
            raise AIError(f"http_{e.code}", retryable=e.code == 429) from e
        except genai_errors.ServerError as e:  # 5xx
            raise AIError(f"http_{e.code}", retryable=True) from e
        except httpx2.HTTPError as e:
            raise AIError("connection", retryable=True) from e

        meta = response.usage_metadata
        usage = TokenUsage(
            model=self.model,
            input_tokens=(meta.prompt_token_count or 0) if meta else 0,
            # Thinking tokens are billed as output.
            output_tokens=((meta.candidates_token_count or 0) + (meta.thoughts_token_count or 0))
            if meta
            else 0,
        )

        finish = response.candidates[0].finish_reason if response.candidates else None
        finish_name = getattr(finish, "name", str(finish)) if finish else None
        if finish_name == "MAX_TOKENS":
            raise AIError("max_tokens", retryable=False, usage=usage)
        if finish_name in {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"}:
            raise AIError("refusal", retryable=False, usage=usage)

        text = response.text
        if not text:
            raise AIError("no_text", retryable=True, usage=usage)
        try:
            result = SummaryResult.model_validate_json(text)
        except ValidationError as e:
            raise AIError("bad_output", retryable=True, usage=usage) from e
        return AIResponse(result=result, usage=usage)


def make_summarizer(provider: str, anthropic_key: str | None, gemini_key: str | None,
                    gemini_model: str = GEMINI_MODEL) -> Summarizer | None:  # fmt: skip
    """None means no key is set: runs then end "Failed, nothing posted."."""
    if provider == "gemini":
        return GeminiSummarizer(gemini_key, gemini_model) if gemini_key else None
    if provider == "claude":
        return ClaudeSummarizer(anthropic_key) if anthropic_key else None
    raise ValueError(f"Unknown AI_PROVIDER: {provider!r} (use 'gemini' or 'claude')")

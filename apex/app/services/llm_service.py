import json
from collections.abc import AsyncGenerator
from typing import Any

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.exceptions import LLMError
from app.core.logging import get_logger

logger = get_logger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def chat(
    messages: list[dict[str, Any]],
    system: str | None = None,
    max_tokens: int | None = None,
    temperature: float = 0.7,
) -> str:
    client = get_client()
    kwargs: dict[str, Any] = {
        "model": settings.anthropic_model,
        "max_tokens": max_tokens or settings.anthropic_max_tokens,
        "messages": messages,
        "temperature": temperature,
    }
    if system:
        kwargs["system"] = system
    try:
        response = await client.messages.create(**kwargs)
        return response.content[0].text  # type: ignore[union-attr]
    except anthropic.APIError as exc:
        logger.error("llm_api_error", error=str(exc))
        raise LLMError(f"LLM request failed: {exc}") from exc


async def stream_chat(
    messages: list[dict[str, Any]],
    system: str | None = None,
    max_tokens: int | None = None,
) -> AsyncGenerator[str, None]:
    client = get_client()
    kwargs: dict[str, Any] = {
        "model": settings.anthropic_model,
        "max_tokens": max_tokens or settings.anthropic_max_tokens,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system
    try:
        async with client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text
    except anthropic.APIError as exc:
        logger.error("llm_stream_error", error=str(exc))
        raise LLMError(f"LLM stream failed: {exc}") from exc


async def extract_json(
    prompt: str,
    system: str | None = None,
) -> dict[str, Any] | list[Any]:
    """Ask the LLM to return pure JSON and parse it."""
    raw = await chat(
        messages=[{"role": "user", "content": prompt}],
        system=system or "You are a precise data extractor. Return ONLY valid JSON, no markdown.",
        temperature=0.0,
    )
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM returned invalid JSON: {exc}") from exc


async def classify_single(prompt: str, valid_outputs: list[str]) -> str:
    """Call the LLM expecting exactly one token from valid_outputs."""
    result = await chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=5,
    )
    result = result.strip()
    if result not in valid_outputs:
        raise LLMError(f"Unexpected classification output: {result!r}")
    return result

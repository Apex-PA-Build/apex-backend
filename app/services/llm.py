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
async def complete(
    prompt: str,
    model: str | None = None,
    max_tokens: int = 2048,
    system: str | None = None,
) -> str:
    """Simple text completion — used for extraction and classification."""
    try:
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        kwargs: dict[str, Any] = {
            "model": model or settings.model_small,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        response = await get_client().messages.create(**kwargs)
        return response.content[0].text.strip()  # type: ignore[union-attr]
    except anthropic.APIError as e:
        logger.error("llm_error", error=str(e))
        raise LLMError(str(e))


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def extract_json(prompt: str, model: str | None = None) -> Any:
    """Extract structured JSON from a prompt. Returns parsed object."""
    try:
        raw = await complete(prompt, model=model, max_tokens=2048)
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except (json.JSONDecodeError, IndexError) as e:
        logger.warning("json_parse_failed", error=str(e), raw=raw[:200])
        raise LLMError(f"Failed to parse JSON response: {e}")


async def chat_with_tools(
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, Any]],
    model: str | None = None,
    max_tokens: int = 4096,
) -> tuple[str, list[str], list[dict[str, Any]]]:
    """
    Run Claude with tool use in a single turn.
    Returns (final_text, tools_used, tool_calls) where tool_calls can be
    passed back to the caller for execution.
    """
    try:
        response = await get_client().messages.create(
            model=model or settings.model_medium,
            max_tokens=max_tokens,
            system=system,
            tools=tools,  # type: ignore[arg-type]
            messages=messages,
        )

        tools_used: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        text_parts: list[str] = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tools_used.append(block.name)
                tool_calls.append({"id": block.id, "name": block.name, "input": block.input})

        return " ".join(text_parts), tools_used, tool_calls
    except anthropic.APIError as e:
        logger.error("llm_tool_error", error=str(e))
        raise LLMError(str(e))


async def stream_with_tools(
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, Any]],
    model: str | None = None,
    max_tokens: int = 4096,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Stream Claude response with tool use. Yields dicts:
      {"type": "chunk",      "content": str}
      {"type": "tool_start", "name": str, "status": str}
      {"type": "tool_done",  "name": str}
      {"type": "tool_calls", "calls": list}   ← when stop_reason == tool_use
      {"type": "done"}
    """
    try:
        async with get_client().messages.stream(
            model=model or settings.model_medium,
            max_tokens=max_tokens,
            system=system,
            tools=tools,  # type: ignore[arg-type]
            messages=messages,
        ) as stream:
            current_tool_name: str | None = None

            async for event in stream:
                event_type = event.type

                if event_type == "content_block_start":
                    block = event.content_block  # type: ignore[attr-defined]
                    if block.type == "tool_use":
                        current_tool_name = block.name
                        yield {"type": "tool_start", "name": block.name}

                elif event_type == "content_block_delta":
                    delta = event.delta  # type: ignore[attr-defined]
                    if hasattr(delta, "text") and delta.text:
                        yield {"type": "chunk", "content": delta.text}

                elif event_type == "content_block_stop":
                    if current_tool_name:
                        yield {"type": "tool_done", "name": current_tool_name}
                        current_tool_name = None

            final = await stream.get_final_message()

            if final.stop_reason == "tool_use":
                calls = [
                    {"id": b.id, "name": b.name, "input": b.input}
                    for b in final.content
                    if b.type == "tool_use"
                ]
                yield {"type": "tool_calls", "calls": calls, "raw_content": final.content}
            else:
                yield {"type": "done"}

    except anthropic.APIError as e:
        logger.error("llm_stream_error", error=str(e))
        raise LLMError(str(e))

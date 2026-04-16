import json
from typing import Any
from collections.abc import AsyncGenerator
from tenacity import retry, stop_after_attempt, wait_exponential

import anthropic
from anthropic import AsyncAnthropic

from app.core.config import settings
from app.core.exceptions import LLMError
from app.core.logging import get_logger

logger = get_logger(__name__)

_client = None

def get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def chat(
    messages: list[dict[str, Any]],
    system: str | None = None,
    max_tokens: int | None = None,
    temperature: float = 0.7,
) -> str:
    client = get_client()
    
    # Check if thinking mode is requested using claude-3-7-sonnet
    # If thinking is enabled, max_tokens MUST be larger than budget_tokens.
    use_thinking = "claude-3-7-sonnet" in settings.anthropic_model
    budget_tokens = 16000
    
    # Prepare thinking parameters and ensure temperature restrictions
    kwargs = {}
    if use_thinking:
        max_tokens_val = max_tokens or settings.anthropic_max_tokens or 20000
        if max_tokens_val <= budget_tokens:
            max_tokens_val = budget_tokens + 4000
            
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget_tokens}
        # Temperature must be exactly 1.0 when thinking is enabled
        kwargs["temperature"] = 1.0
        kwargs["max_tokens"] = max_tokens_val
    else:
        kwargs["temperature"] = temperature
        kwargs["max_tokens"] = max_tokens or settings.anthropic_max_tokens or 4096
    
    # Translate to Anthropic format
    anthropic_msgs = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "assistant"
        anthropic_msgs.append({"role": role, "content": msg["content"]})
            
    try:
        response = await client.messages.create(
            model=settings.anthropic_model,
            system=system or "",
            messages=anthropic_msgs,
            **kwargs
        )
        
        # Anthropic thinking chunks are returned alongside text chunks
        # Only return the final text block to the user
        text_content = ""
        for block in response.content:
            if block.type == "text":
                text_content += block.text
                
        return text_content
    except Exception as exc:
        logger.error("llm_api_error", error=str(exc))
        raise LLMError(f"LLM request failed: {exc}") from exc

async def stream_chat(
    messages: list[dict[str, Any]],
    system: str | None = None,
    max_tokens: int | None = None,
) -> AsyncGenerator[str, None]:
    client = get_client()
    
    use_thinking = "claude-3-7-sonnet" in settings.anthropic_model
    budget_tokens = 16000
    
    kwargs = {}
    if use_thinking:
        max_tokens_val = max_tokens or settings.anthropic_max_tokens or 20000
        if max_tokens_val <= budget_tokens:
            max_tokens_val = budget_tokens + 4000
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget_tokens}
        kwargs["temperature"] = 1.0
        kwargs["max_tokens"] = max_tokens_val
    else:
        kwargs["temperature"] = 0.7
        kwargs["max_tokens"] = max_tokens or settings.anthropic_max_tokens or 4096
        
    anthropic_msgs = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "assistant"
        anthropic_msgs.append({"role": role, "content": msg["content"]})

    try:
        async with client.messages.stream(
            model=settings.anthropic_model,
            system=system or "",
            messages=anthropic_msgs,
            **kwargs
        ) as stream:
             async for event in stream:
                 # Yield purely the text answers for standard output
                 if event.type == "text_delta":
                     yield event.text
    except Exception as exc:
        logger.error("llm_stream_error", error=str(exc))
        raise LLMError(f"LLM stream failed: {exc}") from exc

async def extract_json(
    prompt: str,
    system: str | None = None,
) -> dict[str, Any] | list[Any]:
    client = get_client()
    
    # Pre-fill response with opening bracket to force JSON
    messages = [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "["}
    ]
    
    sys_prompt = system or "You must output strictly valid JSON format. Provide the raw JSON only without markdown code blocks."
    
    try:
        response = await client.messages.create(
            model=settings.anthropic_model,
            system=sys_prompt,
            messages=messages,
            max_tokens=4000,
            temperature=0.0
        )
        
        # We forced a leading bracket, so reattach it
        raw = "[" + response.content[0].text.strip()
        
        # Anthropic sometimes adds markdown codeblocks even when we force it, strip them out just in case
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.endswith("```"):
            raw = raw[:-3]
            
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM returned invalid JSON: {exc}") from exc
    except Exception as exc:
        logger.error("llm_api_error", error=str(exc))
        raise LLMError(f"LLM request failed: {exc}") from exc

async def classify_single(prompt: str, valid_outputs: list[str]) -> str:
    client = get_client()
    try:
        response = await client.messages.create(
            model=settings.anthropic_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=5,
            temperature=0.0
        )
        result = response.content[0].text.strip()
        if result not in valid_outputs:
            raise LLMError(f"Unexpected classification output: {result!r}")
        return result
    except Exception as exc:
        logger.error("llm_api_error", error=str(exc))
        raise LLMError(f"Classification failed: {exc}") from exc

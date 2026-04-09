import json
import google.generativeai as genai
from typing import Any
from collections.abc import AsyncGenerator
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.exceptions import LLMError
from app.core.logging import get_logger

logger = get_logger(__name__)

_client_configured = False

def get_client() -> None:
    global _client_configured
    if not _client_configured:
        genai.configure(api_key=settings.gemini_api_key)
        _client_configured = True

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def chat(
    messages: list[dict[str, Any]],
    system: str | None = None,
    max_tokens: int | None = None,
    temperature: float = 0.7,
) -> str:
    get_client()
    model = genai.GenerativeModel(settings.gemini_model, system_instruction=system)
    
    history = []
    current_message = ""
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        if msg == messages[-1]:
            current_message = msg["content"]
        else:
            history.append({"role": role, "parts": [msg["content"]]})
            
    try:
        if history:
            chat_session = model.start_chat(history=history)
            response = await chat_session.send_message_async(
                current_message,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens or 4096,
                )
            )
        else:
            response = await model.generate_content_async(
                current_message,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens or 4096,
                )
            )
        return response.text
    except Exception as exc:
        logger.error("llm_api_error", error=str(exc))
        raise LLMError(f"LLM request failed: {exc}") from exc

async def stream_chat(
    messages: list[dict[str, Any]],
    system: str | None = None,
    max_tokens: int | None = None,
) -> AsyncGenerator[str, None]:
    get_client()
    model = genai.GenerativeModel(settings.gemini_model, system_instruction=system)
    
    history = []
    current_message = ""
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        if msg == messages[-1]:
            current_message = msg["content"]
        else:
            history.append({"role": role, "parts": [msg["content"]]})

    try:
        if history:
            chat_session = model.start_chat(history=history)
            response = await chat_session.send_message_async(
                current_message,
                stream=True,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=max_tokens or 4096,
                )
            )
        else:
            response = await model.generate_content_async(
                current_message,
                stream=True,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=max_tokens or 4096,
                )
            )
        async for chunk in response:
            if chunk.text:
                yield chunk.text
    except Exception as exc:
        logger.error("llm_stream_error", error=str(exc))
        raise LLMError(f"LLM stream failed: {exc}") from exc

async def extract_json(
    prompt: str,
    system: str | None = None,
) -> dict[str, Any] | list[Any]:
    get_client()
    
    model = genai.GenerativeModel(settings.gemini_model, system_instruction=system)
    try:
        response = await model.generate_content_async(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.0,
                response_mime_type="application/json",
            )
        )
        raw = response.text.strip()
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM returned invalid JSON: {exc}") from exc
    except Exception as exc:
        logger.error("llm_api_error", error=str(exc))
        raise LLMError(f"LLM request failed: {exc}") from exc

async def classify_single(prompt: str, valid_outputs: list[str]) -> str:
    result = await chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=5,
    )
    result = result.strip()
    if result not in valid_outputs:
        raise LLMError(f"Unexpected classification output: {result!r}")
    return result

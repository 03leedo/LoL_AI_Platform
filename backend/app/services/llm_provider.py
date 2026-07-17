"""Provider-agnostic JSON generation for report writing (M3).

The LLM is a *writer*, not an analyst: it receives rule-computed patterns and
scores and returns Korean prose in a fixed JSON shape. Providers: any
OpenAI-compatible endpoint (existing config) or Anthropic. No configured key
-> LlmProviderError, and callers fall back to the deterministic report.
"""

import json
import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 45.0
# Thinking-style models (e.g. Gemini 3.5 Flash) spend part of this budget on
# reasoning before emitting JSON — keep headroom so output is not truncated.
MAX_OUTPUT_TOKENS = 4000


class LlmProviderError(Exception):
    pass


def provider_available() -> bool:
    settings = get_settings()
    if settings.llm_provider == "anthropic":
        return bool(settings.anthropic_api_key)
    return bool(settings.openai_api_key)


async def generate_json(system_prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise LlmProviderError("ANTHROPIC_API_KEY is not configured")
        text = await _anthropic_generate(system_prompt, payload)
    else:
        if not settings.openai_api_key:
            raise LlmProviderError("OPENAI_API_KEY is not configured")
        text = await _openai_generate(system_prompt, payload)

    return _parse_json(text)


async def _openai_generate(system_prompt: str, payload: dict[str, Any]) -> str:
    settings = get_settings()
    url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"
    body = {
        "model": settings.openai_model,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    }
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}

    data = await _post_json(url, headers, body)
    usage = data.get("usage") or {}
    logger.info(
        "LLM usage: provider=openai-compat model=%s total_tokens=%s",
        settings.openai_model,
        usage.get("total_tokens"),
    )
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmProviderError(f"Unexpected OpenAI response shape: {exc}") from exc


async def _anthropic_generate(system_prompt: str, payload: dict[str, Any]) -> str:
    settings = get_settings()
    url = f"{settings.anthropic_base_url.rstrip('/')}/v1/messages"
    body = {
        "model": settings.anthropic_model,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    }
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
    }

    data = await _post_json(url, headers, body)
    usage = data.get("usage") or {}
    logger.info(
        "LLM usage: provider=anthropic model=%s input_tokens=%s output_tokens=%s",
        settings.anthropic_model,
        usage.get("input_tokens"),
        usage.get("output_tokens"),
    )
    try:
        blocks = data["content"]
        text = "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
    except (KeyError, TypeError) as exc:
        raise LlmProviderError(f"Unexpected Anthropic response shape: {exc}") from exc
    if not text:
        raise LlmProviderError("Anthropic response contained no text")
    return text


async def _post_json(url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise LlmProviderError(f"LLM request failed: {exc}") from exc

    if response.status_code >= 400:
        raise LlmProviderError(f"LLM provider returned HTTP {response.status_code}")

    try:
        return response.json()
    except ValueError as exc:
        raise LlmProviderError("LLM provider returned non-JSON body") from exc


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    try:
        parsed = json.loads(cleaned)
    except ValueError as exc:
        raise LlmProviderError("LLM output was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise LlmProviderError("LLM output was not a JSON object")
    return parsed

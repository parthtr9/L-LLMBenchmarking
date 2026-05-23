"""Async LiteLLM wrapper returning normalized results."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import litellm
from litellm.exceptions import (
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
)
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

_THINK_RE = re.compile(r"(?:<think>)?(.*?)</think>\s*", flags=re.DOTALL)

# Suppress litellm's noisy default logging.
litellm.suppress_debug_info = True


@dataclass
class LiteLLMResult:
    """Normalized response from any LiteLLM-backed provider."""

    raw_text: str | None
    reasoning_text: str | None
    usage: dict[str, Any] | None
    latency_s: float | None
    error: str | None


def _split_reasoning(raw: str) -> tuple[str | None, str]:
    """Strip Qwen <think>…</think> traces from the final answer."""
    match = _THINK_RE.search(raw)
    if match and "</think>" in raw:
        return match.group(1).strip(), raw[match.end() :].strip()
    return None, raw.strip()


_NO_RETRY = (BadRequestError, AuthenticationError, NotFoundError, PermissionDeniedError)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(min=1, max=30),
    retry=retry_if_not_exception_type(_NO_RETRY),
)
async def _call(**kwargs: Any) -> Any:
    return await litellm.acompletion(**kwargs)


async def acomplete(
    messages: list[dict[str, str]],
    model: str,
    api_base: str | None = None,
    api_key: str | None = None,
    extra_body: dict[str, Any] | None = None,
    max_tokens: int = 500,
    temperature: float = 0.0,
    timeout: float = 900.0,
    seed: int = 42,
) -> LiteLLMResult:
    """Call any LiteLLM-supported provider with retry. Return normalized result."""
    # OpenAI SDK requires base_url to end with /v1 for custom endpoints.
    if api_base and not api_base.rstrip("/").endswith("/v1"):
        api_base = api_base.rstrip("/") + "/v1"

    started = time.perf_counter()
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "timeout": timeout,
        # seed omitted: not supported by all providers (e.g. vLLM HF endpoints)
    }
    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key
    if extra_body:
        kwargs["extra_body"] = extra_body

    try:
        response = await _call(**kwargs)
    except Exception as exc:
        logger.exception("litellm call failed for model=%s", model)
        return LiteLLMResult(
            raw_text=None,
            reasoning_text=None,
            usage=None,
            latency_s=time.perf_counter() - started,
            error=str(exc),
        )

    latency = time.perf_counter() - started
    message = response.choices[0].message
    raw = (message.content or "").strip()
    reasoning: str | None = getattr(message, "reasoning_content", None)
    if not reasoning:
        reasoning, raw = _split_reasoning(raw)

    usage_obj = getattr(response, "usage", None)
    usage: dict[str, Any] | None = None
    if usage_obj:
        try:
            usage = dict(usage_obj)
        except TypeError:
            usage = {
                "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0),
                "completion_tokens": getattr(usage_obj, "completion_tokens", 0),
                "total_tokens": getattr(usage_obj, "total_tokens", 0),
            }

    return LiteLLMResult(
        raw_text=raw,
        reasoning_text=reasoning,
        usage=usage,
        latency_s=latency,
        error=None,
    )

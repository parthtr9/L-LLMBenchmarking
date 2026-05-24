"""Custom Inspect AI solvers backed by LiteLLM."""

from __future__ import annotations

import asyncio
import logging
import os
import random
from typing import Any

from inspect_ai.model import ModelOutput, ModelUsage
from inspect_ai.solver import Generate, TaskState, solver

from .litellm_client import LiteLLMResult, acomplete

logger = logging.getLogger(__name__)


def _content_to_str(content: Any) -> str:
    """Normalize Inspect ChatMessage content (str or list[Content]) to plain text."""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for item in content:
        if hasattr(item, "text"):
            parts.append(item.text)
        elif isinstance(item, str):
            parts.append(item)
    return "".join(parts)


def _state_messages_to_litellm(state: TaskState) -> list[dict[str, str]]:
    return [
        {"role": m.role, "content": _content_to_str(m.content)}
        for m in state.messages
    ]


def _result_to_output(result: LiteLLMResult, model_id: str) -> ModelOutput:
    output = ModelOutput.from_content(model=model_id, content=result.raw_text or "")
    if result.usage:
        output.usage = ModelUsage(
            input_tokens=result.usage.get("prompt_tokens", 0),
            output_tokens=result.usage.get("completion_tokens", 0),
            total_tokens=result.usage.get("total_tokens", 0),
        )
    return output


@solver
def litellm_solver(
    model_cfg: dict[str, Any],
    dry_run: bool = False,
    max_tokens: int = 500,
    temperature: float = 0.0,
    timeout: float = 900.0,
    seed: int = 42,
):
    """Inspect solver that routes all generation through LiteLLM.

    Args:
        model_cfg: Entry from config/models.yaml (already loaded as dict).
        dry_run: Skip model calls; return placeholder output for pipeline testing.
        max_tokens: Max output tokens per call.
        temperature: Sampling temperature.
        timeout: Per-request timeout in seconds.
        seed: Random seed passed to provider where supported.
    """
    model_id: str = model_cfg["litellm_model"]
    api_base: str | None = (
        os.getenv(model_cfg["api_base_env"]) if "api_base_env" in model_cfg else None
    )
    api_key: str | None = (
        os.getenv(model_cfg["api_key_env"]) if "api_key_env" in model_cfg else None
    )
    extra_body: dict[str, Any] | None = model_cfg.get("extra_body")
    max_concurrency: int = model_cfg.get("max_concurrency", 8)
    semaphore = asyncio.Semaphore(max_concurrency)

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        if dry_run:
            state.output = ModelOutput.from_content(
                model=model_id, content="__dry_run__"
            )
            state.completed = True
            return state

        messages = _state_messages_to_litellm(state)
        async with semaphore:
            result = await acomplete(
                messages=messages,
                model=model_id,
                api_base=api_base,
                api_key=api_key,
                extra_body=extra_body,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=timeout,
                seed=seed,
            )
        state.output = _result_to_output(result, model_id)
        if state.metadata is None:
            state.metadata = {}
        state.metadata.update(
            {
                "litellm_error": result.error,
                "latency_s": result.latency_s,
                "reasoning": result.reasoning_text,
                "usage": result.usage,
            }
        )
        state.completed = True
        return state

    return solve


_FORMAT_RANDOM_CHOICES: dict[str, list[str]] = {
    "mcq":      ["A", "B", "C"],
    "binary":   ["A", "B"],
    "pairwise": ["A", "B"],
}


@solver
def random_baseline_solver(seed: int = 42):
    """Emit a random valid label sampled uniformly from the format's label set."""
    rng = random.Random(seed)

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        fmt = str((state.metadata or {}).get("format", "")).lower()
        choices = _FORMAT_RANDOM_CHOICES.get(fmt, ["A", "B"])
        answer = rng.choice(choices)
        state.output = ModelOutput.from_content(model="random_baseline", content=answer)
        state.completed = True
        return state

    return solve


@solver
def majority_baseline_solver(fmt_majority: dict[str, str]):
    """Always predict the majority label for the sample's format.

    Args:
        fmt_majority: Map of format → most-frequent label in the training split.
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        fmt = str((state.metadata or {}).get("format", "")).lower()
        label = fmt_majority.get(fmt, fmt_majority.get("default", "A"))
        state.output = ModelOutput.from_content(
            model="majority_baseline", content=label
        )
        state.completed = True
        return state

    return solve

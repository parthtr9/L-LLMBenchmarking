"""Custom Inspect AI solvers backed by LiteLLM."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_CACHE = _ROOT / "outputs" / "prediction_cache.json"

import re
from pathlib import Path
from typing import Any

import pandas as pd
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


_LETTER_SETS: dict[str, str] = {
    "mcq":      "ABCD",
    "binary":   "AB",
    "pairwise": "AB",
    "ternary":  "ABC",
}

_ANSWER_MARKER_PATTERNS: list[str] = [
    r"\\boxed\{\s*([A-D])\s*\}",
    r"final\s+answer\s*[:\-=]\s*\**\s*([A-D])\s*\**",
    r"answer\s*[:\-=]\s*\**\s*([A-D])\s*\**",
    r"the\s+(?:correct\s+)?(?:answer|choice|option)\s+is\s*\**\s*([A-D])\s*\**",
    r"</think>\s*\**\s*([A-D])\b",
]

_BOUNDARY_LETTER_RE = re.compile(r"(?<![A-Za-z])([A-D])(?![A-Za-z])")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _coerce_to_format(text: str, fmt: str) -> tuple[str, bool]:
    """Coerce raw model output into a format-valid string.

    Forces:
      mcq → single letter A-D
      binary / pairwise → single letter A or B
      ternary → single letter A-C
      regression → single numeric token (integer string)

    Returns (coerced_text, was_coerced). If the raw text is already a clean
    valid label, was_coerced is False. Falls back to first valid letter / "0"
    if nothing parseable is found, so the downstream scorer always gets a
    well-formed answer.
    """
    raw = (text or "").strip()
    fmt = (fmt or "").lower()

    if fmt in _LETTER_SETS:
        valid = _LETTER_SETS[fmt]

        # already-valid single letter
        if len(raw) == 1 and raw.upper() in valid:
            return raw.upper(), raw != raw.upper()

        # 1. explicit answer markers (boxed, "answer:", "</think> A", etc.)
        for pat in _ANSWER_MARKER_PATTERNS:
            for m in reversed(re.findall(pat, raw, re.IGNORECASE)):
                if m.upper() in valid:
                    return m.upper(), True

        # 2. last standalone letter in the valid set
        for m in reversed(_BOUNDARY_LETTER_RE.findall(raw)):
            if m.upper() in valid:
                return m.upper(), True

        # 3. nothing parseable — default to first valid letter
        return valid[0], True

    if fmt == "regression":
        nums = _NUMBER_RE.findall(raw)
        if nums:
            # round to int (regression target is an integer string)
            try:
                coerced = str(int(round(float(nums[-1]))))
            except (ValueError, OverflowError):
                coerced = nums[-1]
            return coerced, coerced != raw
        return "0", True

    return raw, False


@solver
def litellm_solver(
    model_cfg: dict[str, Any],
    model_name: str = "",
    dry_run: bool = False,
    max_tokens: int = 500,
    temperature: float = 0.0,
    timeout: float = 900.0,
    seed: int = 42,
):
    """Inspect solver that routes all generation through LiteLLM.

    Args:
        model_cfg: Entry from config/models.yaml (already loaded as dict).
        model_name: Registry key (e.g. "claude_sonnet"). Used to look up prediction cache.
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

    # Load prediction cache once at solver-init time.
    _cache: dict[str, dict] = {}
    if model_name and _DEFAULT_CACHE.exists():
        try:
            payload = json.loads(_DEFAULT_CACHE.read_text(encoding="utf-8"))
            _cache = payload.get("entries", {})
            logger.info(
                "prediction cache loaded: %d entries (model=%s)", len(_cache), model_name
            )
        except Exception as exc:
            logger.warning("could not load prediction cache: %s", exc)

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        # Cache lookup — skip API call if this (model, lb_id) was already evaluated.
        lb_id = (state.metadata or {}).get("lb_id")
        if model_name and lb_id and _cache:
            hit = _cache.get(f"{model_name}::{lb_id}")
            if hit and hit.get("pred"):
                logger.debug("cache hit: %s::%s", model_name, lb_id)
                fmt = str((state.metadata or {}).get("format", "")).lower()
                coerced_pred, _ = _coerce_to_format(hit["pred"], fmt)
                state.output = ModelOutput.from_content(
                    model=model_id, content=coerced_pred
                )
                if state.metadata is None:
                    state.metadata = {}
                state.metadata.update(
                    {
                        "litellm_error": None,
                        "latency_s": hit.get("latency_s"),
                        "reasoning": hit.get("trace"),
                        "usage": None,
                        "cache_hit": True,
                    }
                )
                state.completed = True
                return state

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

        # Format-coercion harness: force output to be a valid label for the
        # sample's format (MCQ letter, binary letter, integer for regression).
        # Thinking models often leak chain-of-thought past the answer; this
        # guarantees the scorer never sees an unparseable completion.
        fmt = str(state.metadata.get("format", "")).lower()
        raw_completion = state.output.completion or ""
        coerced, was_coerced = _coerce_to_format(raw_completion, fmt)
        if was_coerced:
            usage = state.output.usage
            state.output = ModelOutput.from_content(model=model_id, content=coerced)
            state.output.usage = usage
            logger.debug(
                "coerced output (fmt=%s) raw=%r → %r",
                fmt, raw_completion[:80], coerced,
            )

        state.metadata.update(
            {
                "litellm_error": result.error,
                "latency_s": result.latency_s,
                "reasoning": result.reasoning_text,
                "usage": result.usage,
                "raw_completion": raw_completion,
                "format_coerced": was_coerced,
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
def random_baseline_solver(seed: int = 42, regression_range: tuple[int, int] = (20, 90)):
    """Emit a random valid label sampled uniformly from the format's label set.

    For regression format, samples a random integer uniformly from regression_range
    (derived from training target min/max) instead of a letter.
    """
    rng = random.Random(seed)

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        fmt = str((state.metadata or {}).get("format", "")).lower()
        if fmt == "regression":
            answer = str(rng.randint(regression_range[0], regression_range[1]))
        else:
            choices = _FORMAT_RANDOM_CHOICES.get(fmt, ["A", "B"])
            answer = rng.choice(choices)
        state.output = ModelOutput.from_content(model="random_baseline", content=answer)
        state.completed = True
        return state

    return solve


_SEX_RE = re.compile(r"sex\s*:\s*(male|female)", re.IGNORECASE)
_CENSUS_SEX_CODE = {"male": 1, "female": 2}


def _load_census_weights(
    csv_path: Path,
    year_col: str,
    age_min: int,
    age_max: int,
) -> dict[int, tuple[list[int], list[float]]]:
    """Load Census nc-est CSV into per-sex (ages, weights) tables.

    Keys: 0 (both), 1 (male), 2 (female). Drops AGE=999 (all-ages total row).
    """
    df = pd.read_csv(csv_path)
    df = df[(df["AGE"] >= age_min) & (df["AGE"] <= age_max) & (df["AGE"] != 999)]
    out: dict[int, tuple[list[int], list[float]]] = {}
    for sex_code in (0, 1, 2):
        sub = df[df["SEX"] == sex_code]
        ages = sub["AGE"].astype(int).tolist()
        weights = sub[year_col].astype(float).tolist()
        out[sex_code] = (ages, weights)
    return out


@solver
def population_prior_baseline_solver(
    csv_path: str,
    year_col: str = "POPESTIMATE2025",
    age_min: int = 20,
    age_max: int = 90,
    seed: int = 42,
):
    """Sample age from US Census population distribution conditioned on sex.

    Regression-format only. For other formats falls back to random label draw.
    Sex parsed from the user message (`Sex: Male/Female`); falls back to
    both-sex (SEX=0) prior when not present.

    Args:
        csv_path: Path to Census nc-est CSV (cols SEX, AGE, POPESTIMATE<year>).
        year_col: Column to weight the sample by.
        age_min: Lower clip on age (matches plausible cohort range).
        age_max: Upper clip on age.
        seed: RNG seed.
    """
    weights = _load_census_weights(Path(csv_path), year_col, age_min, age_max)
    rng = random.Random(seed)
    fallback_choices = _FORMAT_RANDOM_CHOICES

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        fmt = str((state.metadata or {}).get("format", "")).lower()

        if fmt != "regression":
            choices = fallback_choices.get(fmt, ["A", "B"])
            answer = rng.choice(choices)
            state.output = ModelOutput.from_content(
                model="population_prior_baseline", content=answer
            )
            state.completed = True
            return state

        sex_code = 0
        for msg in state.messages:
            text = msg.content if isinstance(msg.content, str) else _content_to_str(
                msg.content
            )
            m = _SEX_RE.search(text)
            if m:
                sex_code = _CENSUS_SEX_CODE[m.group(1).lower()]
                break

        ages, w = weights.get(sex_code) or weights[0]
        age = rng.choices(ages, weights=w, k=1)[0]
        state.output = ModelOutput.from_content(
            model="population_prior_baseline", content=str(int(age))
        )
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

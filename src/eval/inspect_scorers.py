"""Inspect AI scorers for LongevityBench-X tasks."""

from __future__ import annotations

import re

from inspect_ai.scorer import Score, Target, mean, scorer
from inspect_ai.solver import TaskState

_ANSWER_LETTER_RE = re.compile(r"(?<![A-Za-z])([A-F])(?![A-Za-z])")


def _extract_mcq_letter(text: str) -> str | None:
    letters = _ANSWER_LETTER_RE.findall(text)
    return letters[-1] if letters else None


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().strip('"').strip("'").lower())


@scorer(metrics=[mean()])
def longebench_scorer() -> ...:
    """Format-aware scorer for LongevityBench tasks (mcq, binary, pairwise).

    Score.value: 0.0 or 1.0 exact match for all supported formats.
    """

    async def score(state: TaskState, target: Target) -> Score:
        completion = ""
        if state.output and state.output.completion:
            completion = state.output.completion

        gold = target.text
        meta = state.metadata or {}
        fmt = str(meta.get("format", "")).lower()

        # --- MCQ ---
        if "mcq" in fmt or "multiple" in fmt:
            pred = _extract_mcq_letter(completion) or _normalize(completion)
            correct = _normalize(pred) == _normalize(gold)
            return Score(
                value=1.0 if correct else 0.0,
                answer=pred,
                explanation=f"pred={pred!r} gold={gold!r}",
            )

        # --- default: normalized exact match (binary, pairwise, unknown) ---
        pred_norm = _normalize(completion)
        gold_norm = _normalize(gold)
        correct = pred_norm == gold_norm
        return Score(
            value=1.0 if correct else 0.0,
            answer=pred_norm,
            explanation=f"pred={pred_norm!r} gold={gold_norm!r}",
        )

    return score


# Placeholder for future trace faithfulness scorer.
# trace_faithfulness_scorer will be implemented in src/trace_scorer/trace_scorer.py
# and wired here once the entity extractor + verifiers are complete.

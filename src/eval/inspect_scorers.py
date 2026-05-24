"""Inspect AI scorers for LongevityBench-X tasks."""

from __future__ import annotations

import re

from inspect_ai.scorer import Score, Target, mean, scorer
from inspect_ai.solver import TaskState

_ANSWER_LETTER_RE = re.compile(r"(?<![A-Za-z])([A-F])(?![A-Za-z])")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _extract_mcq_letter(text: str) -> str | None:
    letters = _ANSWER_LETTER_RE.findall(text)
    return letters[-1] if letters else None


def _extract_number(text: str) -> float | None:
    m = _NUMBER_RE.search(text.strip())
    return float(m.group()) if m else None


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().strip('"').strip("'").lower())


@scorer(metrics=[mean()])
def longebench_scorer() -> ...:
    """Format-aware scorer for LongevityBench tasks (mcq, binary, pairwise, regression).

    Score.value:
      regression — 1 / (1 + MAE) so higher = better; raw MAE stored in metadata.
      all others — 0.0 or 1.0 exact match.
    """

    async def score(state: TaskState, target: Target) -> Score:
        completion = ""
        if state.output and state.output.completion:
            completion = state.output.completion

        gold = target.text
        meta = state.metadata or {}
        fmt = str(meta.get("format", "")).lower()

        # --- Regression (MAE) ---
        if fmt == "regression":
            gold_val = _extract_number(gold)
            pred_val = _extract_number(completion)
            if gold_val is None or pred_val is None:
                mae = None
                value = 0.0
                explanation = f"parse_fail pred={completion!r} gold={gold!r}"
            else:
                mae = abs(pred_val - gold_val)
                value = round(1.0 / (1.0 + mae), 4)
                explanation = f"pred={pred_val} gold={gold_val} mae={mae:.2f}"
            return Score(
                value=value,
                answer=str(pred_val),
                explanation=explanation,
                metadata={"mae": mae, "pred": pred_val, "gold": gold_val},
            )

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

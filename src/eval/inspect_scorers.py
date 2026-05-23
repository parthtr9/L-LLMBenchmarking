"""Inspect AI scorers for LongevityBench-X tasks."""

from __future__ import annotations

import re

from inspect_ai.scorer import Score, Target, mean, scorer
from inspect_ai.solver import TaskState

_ANSWER_LETTER_RE = re.compile(r"(?<![A-Za-z])([A-F])(?![A-Za-z])")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _extract_number(text: str) -> float | None:
    m = _NUMBER_RE.search(text)
    return float(m.group()) if m else None


def _extract_mcq_letter(text: str) -> str | None:
    letters = _ANSWER_LETTER_RE.findall(text)
    return letters[-1] if letters else None


def _parse_set(value: str) -> set[str]:
    return {item.strip().lower() for item in re.split(r"[,;\n]", value) if item.strip()}


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().strip('"').strip("'").lower())


@scorer(metrics=[mean()])
def longebench_scorer() -> ...:
    """Format-aware scorer for LongeBench tasks.

    Uses Score.value semantics:
    - Classification / MCQ / Jaccard: 0.0 or 1.0 (exact match) / continuous [0,1]
    - Regression: 1 / (1 + mae) so higher = better; raw MAE stored in metadata
    """

    async def score(state: TaskState, target: Target) -> Score:
        completion = ""
        if state.output and state.output.completion:
            completion = state.output.completion

        gold = target.text
        meta = state.metadata or {}
        fmt = str(meta.get("format", "")).lower()
        metric = str(meta.get("metric", "")).lower()

        # --- regression / MAE ---
        if "mae" in metric or "regression" in fmt:
            pred = _extract_number(completion)
            gold_num = _extract_number(gold)
            if pred is None or gold_num is None:
                return Score(
                    value=0.0,
                    answer=completion,
                    explanation="parse_error: could not extract number",
                    metadata={"mae": None, "pred": None, "gold": gold},
                )
            mae = abs(pred - gold_num)
            return Score(
                value=1.0 / (1.0 + mae),
                answer=str(pred),
                explanation=f"pred={pred} gold={gold_num} mae={mae:.2f}",
                metadata={"mae": mae, "pred": pred, "gold": gold_num},
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

        # --- set generation / Jaccard ---
        if "jaccard" in metric or "set" in fmt:
            pred_set = _parse_set(completion)
            gold_set = _parse_set(gold)
            denom = len(pred_set | gold_set)
            jaccard = len(pred_set & gold_set) / denom if denom else 0.0
            return Score(
                value=jaccard,
                answer=completion,
                explanation=f"jaccard={jaccard:.3f} pred={pred_set} gold={gold_set}",
            )

        # --- default: normalized exact match ---
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

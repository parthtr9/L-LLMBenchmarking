"""Inspect AI scorers for LongevityBench-X tasks."""

from __future__ import annotations

import math
import re
from collections import defaultdict

from inspect_ai.scorer import (
    Metric,
    SampleScore,
    Score,
    Target,
    mean,
    metric,
    scorer,
)
from inspect_ai.solver import TaskState

_ANSWER_LETTER_RE = re.compile(r"(?<![A-Za-z])([A-F])(?![A-Za-z])")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")

# MCQ letter -> ordinal index for age brackets (Task B). A=0, B=1, C=2, D=3.
_LETTER_TO_INDEX = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5}


def _extract_mcq_letter(text: str) -> str | None:
    letters = _ANSWER_LETTER_RE.findall(text)
    return letters[-1] if letters else None


def _extract_number(text: str) -> float | None:
    m = _NUMBER_RE.search(text.strip())
    return float(m.group()) if m else None


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().strip('"').strip("'").lower())


def _off_by_one_score(pred_letter: str | None, gold_letter: str | None) -> float:
    """Graded score for ordinal MCQ.

    1.0 exact, 0.5 if adjacent (|Δ| == 1), 0.0 otherwise. 0.0 on parse failure.
    """
    if pred_letter is None or gold_letter is None:
        return 0.0
    pi = _LETTER_TO_INDEX.get(pred_letter.upper())
    gi = _LETTER_TO_INDEX.get(gold_letter.upper())
    if pi is None or gi is None:
        return 0.0
    delta = abs(pi - gi)
    if delta == 0:
        return 1.0
    if delta == 1:
        return 0.5
    return 0.0


@metric
def balanced_accuracy() -> Metric:
    """Mean of per-class accuracy across gold-label classes.

    Filters to rows whose `metric` field equals 'balanced accuracy' so that
    other formats in the same eval do not pollute the average. Each row
    contributes 1.0 / 0.0 (correct/incorrect) into its own gold class;
    classes are then averaged uniformly. nan when no applicable rows.
    """

    def fn(scores: list[SampleScore]) -> float:
        per_class: dict[str, list[float]] = defaultdict(list)
        for s in scores:
            sm = s.sample_metadata or {}
            if str(sm.get("metric", "")).lower() != "balanced accuracy":
                continue
            gold = (s.score.metadata or {}).get("gold")
            if gold is None:
                continue
            per_class[str(gold)].append(float(s.score.value))
        if not per_class:
            return float("nan")
        return sum(sum(v) / len(v) for v in per_class.values()) / len(per_class)

    return fn


@metric
def off_by_one_accuracy() -> Metric:
    """Mean of graded off-by-one scores (1.0 / 0.5 / 0.0).

    Filters to rows whose `metric` field equals 'off-by-one accuracy'.
    Per-sample value is already graded by the scorer, so this is just
    a filtered mean. nan when no applicable rows.
    """

    def fn(scores: list[SampleScore]) -> float:
        vals = [
            float(s.score.value)
            for s in scores
            if str((s.sample_metadata or {}).get("metric", "")).lower()
            == "off-by-one accuracy"
        ]
        if not vals:
            return float("nan")
        return sum(vals) / len(vals)

    return fn


@metric
def mae() -> Metric:
    """Mean absolute error for regression rows.

    Reads raw MAE from `score.metadata['mae']` (the scorer stores it there;
    `score.value` is 1/(1+MAE) so unfiltered means stay in [0,1]). nan when
    no applicable rows.
    """

    def fn(scores: list[SampleScore]) -> float:
        vals: list[float] = []
        for s in scores:
            sm = s.sample_metadata or {}
            if str(sm.get("metric", "")).lower() != "mae":
                continue
            m = (s.score.metadata or {}).get("mae")
            if m is None or (isinstance(m, float) and math.isnan(m)):
                continue
            vals.append(float(m))
        if not vals:
            return float("nan")
        return sum(vals) / len(vals)

    return fn


@scorer(metrics=[mean(), balanced_accuracy(), off_by_one_accuracy(), mae()])
def longebench_scorer() -> ...:
    """Format-aware scorer for LongevityBench tasks.

    Score.value semantics (so unfiltered mean stays in [0,1] and is
    interpretable):
      regression           -> 1 / (1 + MAE). Raw MAE in score.metadata['mae'].
      off-by-one accuracy  -> 1.0 / 0.5 / 0.0 graded by bracket distance.
      balanced accuracy    -> 1.0 / 0.0 exact match. The balanced_accuracy
                              aggregate metric class-averages across gold.
      accuracy             -> 1.0 / 0.0 exact match.
    """

    async def score(state: TaskState, target: Target) -> Score:
        completion = ""
        if state.output and state.output.completion:
            completion = state.output.completion

        gold = target.text
        meta = state.metadata or {}
        fmt = str(meta.get("format", "")).lower()
        metric_name = str(meta.get("metric", "")).lower()

        # --- Regression (MAE) ---
        if fmt == "regression" or metric_name == "mae":
            gold_val = _extract_number(gold)
            pred_val = _extract_number(completion)
            if gold_val is None or pred_val is None:
                mae_val = None
                value = 0.0
                explanation = f"parse_fail pred={completion!r} gold={gold!r}"
            else:
                mae_val = abs(pred_val - gold_val)
                value = round(1.0 / (1.0 + mae_val), 4)
                explanation = f"pred={pred_val} gold={gold_val} mae={mae_val:.2f}"
            return Score(
                value=value,
                answer=str(pred_val),
                explanation=explanation,
                metadata={"mae": mae_val, "pred": pred_val, "gold": gold_val},
            )

        # --- Off-by-one MCQ (Task B age brackets) ---
        if metric_name == "off-by-one accuracy":
            pred_letter = _extract_mcq_letter(completion)
            gold_letter = _extract_mcq_letter(gold) or gold.strip().upper()
            value = _off_by_one_score(pred_letter, gold_letter)
            return Score(
                value=value,
                answer=pred_letter or completion,
                explanation=(
                    f"pred={pred_letter!r} gold={gold_letter!r} value={value:.2f}"
                ),
                metadata={
                    "pred_letter": pred_letter,
                    "gold_letter": gold_letter,
                    "gold": gold_letter,
                    "off_by_one": True,
                },
            )

        # --- Plain MCQ exact match ---
        if "mcq" in fmt or "multiple" in fmt:
            pred = _extract_mcq_letter(completion) or _normalize(completion)
            gold_norm = _normalize(gold)
            pred_norm = _normalize(pred)
            correct = pred_norm == gold_norm
            return Score(
                value=1.0 if correct else 0.0,
                answer=pred,
                explanation=f"pred={pred!r} gold={gold!r}",
                metadata={"gold": gold_norm, "pred": pred_norm},
            )

        # --- Binary / pairwise / unknown: normalized exact match ---
        pred_letter = _extract_mcq_letter(completion)
        pred_norm = _normalize(pred_letter) if pred_letter else _normalize(completion)
        gold_norm = _normalize(gold)
        correct = pred_norm == gold_norm
        return Score(
            value=1.0 if correct else 0.0,
            answer=pred_norm,
            explanation=f"pred={pred_norm!r} gold={gold_norm!r}",
            metadata={"gold": gold_norm, "pred": pred_norm},
        )

    return score


# Placeholder for future trace faithfulness scorer.
# trace_faithfulness_scorer will be implemented in src/trace_scorer/trace_scorer.py
# and wired here once the entity extractor + verifiers are complete.

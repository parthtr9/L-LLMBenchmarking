"""Check whether an L-LLM reasoning trace is consistent with its final answer.

Senescence MCQ mapping:  A = upregulated, B = downregulated, C = no significant change
Binary/pairwise:         A or B (which option)
"""

from __future__ import annotations

_UP = frozenset({
    "upregulated", "up-regulated", "up regulated",
    "increased expression", "overexpressed", "higher expression",
    "elevated", "upregulation", "increases", "was increased",
    "significantly increased", "strongly upregulated",
})
_DOWN = frozenset({
    "downregulated", "down-regulated", "down regulated",
    "decreased expression", "repressed", "lower expression",
    "reduced expression", "suppressed", "downregulation", "decreases",
    "was decreased", "significantly decreased", "strongly downregulated",
})
_NO_CHANGE = frozenset({
    "no significant change", "not significantly changed",
    "no change", "unchanged", "not changed", "no significant",
    "no differential", "no statistically significant",
})


def _has(text: str, phrases: frozenset[str]) -> bool:
    return any(p in text for p in phrases)


def check_consistency(trace: str, pred: str, fmt: str) -> bool:
    """Return True if trace direction is consistent with the predicted label.

    Args:
        trace: raw thinking text from the model
        pred:  extracted final answer (e.g. "A", "B", "C")
        fmt:   question format ("mcq", "binary", "pairwise")

    Returns True when:
    - trace is empty / None (can't determine → assume consistent)
    - format is not mcq (pairwise / binary direction logic differs)
    - trace direction matches predicted label
    Returns False only when there is a clear contradiction.
    """
    if not trace or not pred:
        return True

    t = trace.lower()
    pred = pred.strip().upper()

    if fmt == "mcq":
        says_up = _has(t, _UP)
        says_down = _has(t, _DOWN)
        says_no = _has(t, _NO_CHANGE)

        if pred == "A":  # upregulated
            if says_down and not says_up:
                return False
        elif pred == "B":  # downregulated
            if says_up and not says_down:
                return False
        elif pred == "C":  # no change
            strong_change = (says_up or says_down) and not says_no
            if strong_change:
                return False

    # For binary / pairwise we do not enforce direction — too format-dependent
    return True

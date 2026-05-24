"""Keyword-based trace ↔ answer consistency checker.

Replaces DeBERTa NLI (V2/V3) which gave 3.4% consistency because:
- Biological traces are long; truncation at 1024 chars misses the conclusion
- "the correct choice is A" hypothesis too generic for domain text

Keyword approach (V4):
- Scan full trace for directional keywords (upregulate / downregulate / no change)
- Negation detection: check 50-char window before each match for negation words
- Net direction compared to gold letter → consistency score in [0, 1]

Handles formats:
  mcq      A=up / B=down / C=no_change
  binary   A=significant / B=not_significant
  pairwise returns 0.5 (no directional semantics in A/B labels)
  other    returns 0.5

Score meaning:
  1.0  full directional agreement
  0.5  neutral / ambiguous (no keywords found, or pairwise)
  0.0  directional contradiction
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ── Keyword lists ─────────────────────────────────────────────────────────────

_UP = {
    "upregulat", "up-regulat", "increas", "elevat", "higher", "activat",
    "induc", "promot", "enhanc", "augment", "amplif", "overexpress",
    "upexpressed", "positively regulat", "pro-longevity", "extend",
    "longer lifespan", "lifespan extension", "anti-aging", "anti-senescen",
}

_DOWN = {
    "downregulat", "down-regulat", "decreas", "reduc", "lower", "inhibit",
    "suppress", "diminish", "attenu", "silence", "knockdown", "knock-down",
    "knockout", "ablat", "deplet", "shorten", "pro-aging", "pro-senescen",
    "accelerat", "promotes aging", "shortens lifespan",
}

_NO_CHANGE = {
    "no significant", "not significant", "unchanged", "no change",
    "minimal change", "no effect", "no difference", "no alteration",
    "not altered", "not changed", "not affected",
}

_SIG = {
    "significant", "substantial", "robust", "marked", "pronounced",
    "notably", "considerably", "strongly", "dramatically",
}

_NOT_SIG = {
    "not significant", "non-significant", "negligible", "minimal",
    "no significant", "marginal", "modest effect", "no effect",
}

_NEGATION = re.compile(
    r"\b(not|no|never|doesn't|don't|didn't|cannot|can't|fail|lack|without"
    r"|absence|depleted|deficient|loss of)\b",
    re.IGNORECASE,
)


def _hit_count(trace_lower: str, keywords: set[str]) -> int:
    count = 0
    for kw in keywords:
        for m in re.finditer(re.escape(kw), trace_lower):
            start = max(0, m.start() - 50)
            window = trace_lower[start:m.start()]
            negated = bool(_NEGATION.search(window))
            count += -1 if negated else 1
    return count


def _mcq_score(trace_lower: str, pred: str) -> float:
    up = _hit_count(trace_lower, _UP)
    down = _hit_count(trace_lower, _DOWN)
    no_chg_raw = sum(1 for kw in _NO_CHANGE if kw in trace_lower)

    if up == 0 and down == 0 and no_chg_raw == 0:
        return 0.5  # no signal

    pred_upper = pred.strip().upper()

    if pred_upper == "A":   # upregulated
        if up > 0 and up >= down:
            return 1.0
        if down > 0 and down > up:
            return 0.0
        return 0.5

    if pred_upper == "B":   # downregulated
        if down > 0 and down >= up:
            return 1.0
        if up > 0 and up > down:
            return 0.0
        return 0.5

    if pred_upper == "C":   # no significant change
        if no_chg_raw > 0 and abs(up) <= 1 and abs(down) <= 1:
            return 1.0
        if up > 1 or down > 1:
            return 0.0
        return 0.5

    return 0.5  # unknown letter


def _binary_score(trace_lower: str, pred: str) -> float:
    sig = _hit_count(trace_lower, _SIG)
    not_sig_raw = sum(1 for kw in _NOT_SIG if kw in trace_lower)

    pred_upper = pred.strip().upper()

    if pred_upper == "A":   # significant
        if sig > 0 and not_sig_raw == 0:
            return 1.0
        if not_sig_raw > 0:
            return 0.0
        return 0.5

    if pred_upper == "B":   # not significant
        if not_sig_raw > 0:
            return 1.0
        if sig > 0:
            return 0.0
        return 0.5

    return 0.5


def keyword_score(trace: str, pred: str, fmt: str) -> float:
    """Return keyword consistency score in [0, 1].

    1.0 = trace direction agrees with predicted answer.
    0.5 = neutral (no keywords found, or pairwise/unknown format).
    0.0 = trace direction contradicts predicted answer.
    """
    if not trace or not pred:
        return 0.5

    trace_lower = trace.lower()
    fmt = fmt.lower()

    if fmt == "mcq" or fmt == "ternary":
        return _mcq_score(trace_lower, pred)

    if fmt == "binary":
        return _binary_score(trace_lower, pred)

    # pairwise / regression / unknown — no directional semantics in A/B label
    return 0.5


def check_consistency(trace: str, pred: str, fmt: str) -> bool:
    """Return True if keyword consistency score >= 0.75."""
    return keyword_score(trace, pred, fmt) >= 0.75


# Keep nli_score as alias so trace_scorer.py import doesn't break.
# Callers get keyword score transparently.
nli_score = keyword_score

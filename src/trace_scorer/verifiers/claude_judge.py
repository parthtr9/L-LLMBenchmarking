"""Claude-as-judge for L-LLM thinking traces.

Replaces Groq Llama-3.3-70B (V2, rate-limited) and DeBERTa zero-shot (V2.1, near-random)
with Claude Sonnet structured output via instructor + Pydantic schema.

Returns:
  - pathway_correctness (0–5): does reasoning use correct biological pathways?
  - evidence_use (0–5):         does conclusion follow from cited evidence?
  - claims: list of GeneClaim with direction/predicate/negated fields
  - reasoning: one-paragraph judge rationale

Aggregated scores:
  - pathway_score = pathway_correctness / 5
  - claim_score   = fraction of claims where direction != unknown and not negated

Cache:
  outputs/claude_judge_cache.json keyed by SHA256(trace + pred + fmt)[:20]
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Literal

import instructor
from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_CACHE_PATH = Path("outputs/claude_judge_cache.json")
_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 1024


class GeneClaim(BaseModel):
    entity: str = Field(description="Gene symbol mentioned in the trace.")
    direction: Literal["increase", "decrease", "no_change", "unknown"] = Field(
        description="Direction the trace claims for this gene's regulation/effect."
    )
    predicate: Literal[
        "extends_lifespan",
        "shortens_lifespan",
        "induces_senescence",
        "inhibits_senescence",
        "regulates_aging",
        "other",
    ] = Field(description="What the trace claims about this gene biologically.")
    negated: bool = Field(description="Is the claim negated (e.g. 'does NOT extend')?")


class TraceJudgment(BaseModel):
    claims: list[GeneClaim] = Field(
        default_factory=list,
        description="Discrete biological claims made about specific genes in the trace.",
    )
    pathway_correctness: int = Field(
        ge=0, le=5,
        description="0–5 — does reasoning correctly use known longevity/senescence pathways "
                    "(IIS, mTOR, FOXO, p53, p16/p21, autophagy, etc.)? 5 = textbook correct, "
                    "0 = fabricated or contradictory pathway claims.",
    )
    evidence_use: int = Field(
        ge=0, le=5,
        description="0–5 — does the final answer follow logically from the evidence cited in "
                    "the trace? 5 = airtight, 0 = answer contradicts trace or no reasoning shown.",
    )
    reasoning: str = Field(
        description="One short paragraph explaining the scores above. Be specific about which "
                    "claims are right or wrong.",
    )


class ClaudeJudge:
    """Sends thinking trace + predicted answer to Claude Sonnet, gets structured judgment."""

    def __init__(self, cache_path: Path = _CACHE_PATH, model: str = _MODEL) -> None:
        self._cache_path = cache_path
        self._cache: dict[str, dict] = {}
        self._model = model
        self._client = instructor.from_anthropic(
            AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY")),
            mode=instructor.Mode.ANTHROPIC_TOOLS,
        )
        self._load_cache()

    def _load_cache(self) -> None:
        if self._cache_path.exists():
            try:
                self._cache = json.loads(self._cache_path.read_text(encoding="utf-8"))
            except Exception:
                self._cache = {}

    def save_cache(self) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(
            json.dumps(self._cache, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _cache_key(trace: str, pred: str, fmt: str) -> str:
        h = hashlib.sha256(f"{trace}||{pred}||{fmt}".encode()).hexdigest()[:20]
        return h

    @staticmethod
    def _build_prompt(trace: str, pred: str, gold: str | None, fmt: str) -> str:
        gold_line = f"\nGround-truth answer: {gold}" if gold else ""
        return (
            f"You are auditing a biological reasoning trace produced by an LLM evaluated on a "
            f"longevity/senescence benchmark.\n\n"
            f"Task format: {fmt}\n"
            f"Predicted answer: {pred}{gold_line}\n\n"
            f"--- BEGIN REASONING TRACE ---\n{trace}\n--- END REASONING TRACE ---\n\n"
            f"Extract discrete gene-level claims from the trace and rate the reasoning. "
            f"Be strict: a confident wrong claim is worse than uncertainty. "
            f"If the trace makes no real biological claim, return empty claims and low pathway_correctness."
        )

    async def judge(
        self,
        trace: str,
        pred: str,
        gold: str | None,
        fmt: str,
    ) -> TraceJudgment:
        key = self._cache_key(trace, pred, fmt)
        if key in self._cache:
            return TraceJudgment(**self._cache[key])

        prompt = self._build_prompt(trace, pred, gold, fmt)
        judgment: TraceJudgment = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
            response_model=TraceJudgment,
        )

        self._cache[key] = judgment.model_dump()
        return judgment

    @staticmethod
    def pathway_score(j: TraceJudgment) -> float:
        return j.pathway_correctness / 5.0

    @staticmethod
    def evidence_score(j: TraceJudgment) -> float:
        return j.evidence_use / 5.0

    @staticmethod
    def claim_score(j: TraceJudgment) -> float:
        if not j.claims:
            return 0.5
        valid = sum(
            1 for c in j.claims
            if c.direction != "unknown" and c.predicate != "other" and not c.negated
        )
        return valid / len(j.claims)

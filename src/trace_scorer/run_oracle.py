"""Tier 3 — Claude oracle augmentation for V5 trace scores.

Reads outputs/trace_faithfulness_scores.json (V5 cheap-proxy output),
calls ClaudeJudge on each trace via instructor+Pydantic, and augments
the per_sample list with:
    pathway_score   (judge.pathway_correctness / 5)
    evidence_score  (judge.evidence_use / 5)
    claim_score     (fraction of valid GeneClaim entries)
    judge_reasoning (one-paragraph rationale)
    n_judge_claims  (length of judge.claims list)

Aggregate Spearman is recomputed between cheap faithfulness (Tier 1+2)
and oracle composite (mean of pathway/evidence/claim). This is the
core "cheap vs oracle correlation" number for the submission.

Output overwrites outputs/trace_faithfulness_scores.json (and public
copy) with the oracle fields merged in.

Usage:
    .venv/bin/python -m src.trace_scorer.run_oracle
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

import numpy as np
import scipy.stats
from dotenv import load_dotenv

from .verifiers.claude_judge import ClaudeJudge, TraceJudgment

logger = logging.getLogger(__name__)

_DEFAULT_DATA_JSON = Path(
    "LongevityBench Design System/ui_kits/longevity_bench/public/data.json"
)
_DEFAULT_SCORES = Path("outputs/trace_faithfulness_scores.json")
_PUBLIC_SCORES = Path(
    "LongevityBench Design System/ui_kits/longevity_bench/public/trace_faithfulness_scores.json"
)
_THINKING_MODEL = "longevity_llm_thinking"
_MAX_CONCURRENT = 4


async def _judge_one(
    judge: ClaudeJudge,
    sem: asyncio.Semaphore,
    trace: str,
    pred: str,
    gold: str,
    fmt: str,
) -> TraceJudgment:
    async with sem:
        return await judge.judge(trace, pred, gold, fmt)


async def _run(scores_path: Path, data_path: Path) -> None:
    scores = json.loads(scores_path.read_text(encoding="utf-8"))
    data = json.loads(data_path.read_text(encoding="utf-8"))

    # Index traces by lb_id for quick lookup.
    trace_by_lb: dict[str, str] = {}
    for s in data["samples"]:
        cell = s.get("cells", {}).get(_THINKING_MODEL, {})
        t = cell.get("trace")
        if t:
            trace_by_lb[s["lb_id"]] = t

    judge = ClaudeJudge()
    sem = asyncio.Semaphore(_MAX_CONCURRENT)

    per_sample = scores["per_sample"]
    tasks = []
    target_indices = []
    for idx, r in enumerate(per_sample):
        if not r.get("trace_present"):
            continue
        trace = trace_by_lb.get(r["lb_id"])
        if not trace:
            continue
        tasks.append(_judge_one(judge, sem, trace, r["pred"], r["gold"], r["format"]))
        target_indices.append(idx)

    logger.info("dispatching %d Claude judge calls (concurrency=%d)", len(tasks), _MAX_CONCURRENT)
    judgments: list[TraceJudgment] = await asyncio.gather(*tasks)
    judge.save_cache()

    # Merge judgments into per_sample
    for idx, j in zip(target_indices, judgments):
        per_sample[idx]["pathway_score"] = round(ClaudeJudge.pathway_score(j), 4)
        per_sample[idx]["evidence_score"] = round(ClaudeJudge.evidence_score(j), 4)
        per_sample[idx]["claim_score"] = round(ClaudeJudge.claim_score(j), 4)
        per_sample[idx]["n_judge_claims"] = len(j.claims)
        per_sample[idx]["judge_reasoning"] = j.reasoning
        # Oracle composite — equal weight across the 3 judge axes
        per_sample[idx]["oracle_score"] = round(
            (
                ClaudeJudge.pathway_score(j)
                + ClaudeJudge.evidence_score(j)
                + ClaudeJudge.claim_score(j)
            )
            / 3.0,
            4,
        )

    # Aggregate oracle averages
    oracle_samples = [r for r in per_sample if "oracle_score" in r]
    n = len(oracle_samples)
    avg_pathway = sum(r["pathway_score"] for r in oracle_samples) / n
    avg_evidence = sum(r["evidence_score"] for r in oracle_samples) / n
    avg_claim = sum(r["claim_score"] for r in oracle_samples) / n
    avg_oracle = sum(r["oracle_score"] for r in oracle_samples) / n

    # Spearman: cheap (faithfulness) vs oracle
    cheap = np.array([r["faithfulness"] for r in oracle_samples])
    oracle = np.array([r["oracle_score"] for r in oracle_samples])
    rho_co, p_co = scipy.stats.spearmanr(cheap, oracle)

    # Spearman: oracle vs correctness
    passes = np.array([int(r["pass"]) for r in oracle_samples])
    rho_oa, p_oa = scipy.stats.spearmanr(oracle, passes)

    scores["oracle"] = {
        "model": ClaudeJudge.__module__,
        "n_judged": n,
        "avg_pathway_score": round(avg_pathway, 4),
        "avg_evidence_score": round(avg_evidence, 4),
        "avg_claim_score": round(avg_claim, 4),
        "avg_oracle_score": round(avg_oracle, 4),
        "spearman_cheap_vs_oracle": {
            "rho": round(float(rho_co), 4),
            "p_value": round(float(p_co), 4),
        },
        "spearman_oracle_vs_correctness": {
            "rho": round(float(rho_oa), 4),
            "p_value": round(float(p_oa), 4),
        },
    }

    payload = json.dumps(scores, indent=2)
    scores_path.write_text(payload, encoding="utf-8")
    _PUBLIC_SCORES.parent.mkdir(parents=True, exist_ok=True)
    _PUBLIC_SCORES.write_text(payload, encoding="utf-8")

    print(f"\n{'─'*62}")
    print(f"  Oracle Tier (Claude Sonnet 4.6) · n={n}")
    print(f"{'─'*62}")
    print(f"  Avg pathway:        {avg_pathway:.3f}")
    print(f"  Avg evidence_use:   {avg_evidence:.3f}")
    print(f"  Avg claim_score:    {avg_claim:.3f}")
    print(f"  Avg oracle (mean):  {avg_oracle:.3f}")
    print()
    print(f"  Spearman cheap (V5) vs oracle:        ρ = {rho_co:.3f}   p = {p_co:.4f}")
    print(f"  Spearman oracle vs correctness:       ρ = {rho_oa:.3f}   p = {p_oa:.4f}")
    print(f"{'─'*62}\n")


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", type=Path, default=_DEFAULT_SCORES)
    parser.add_argument("--data-json", type=Path, default=_DEFAULT_DATA_JSON)
    args = parser.parse_args()

    if not args.scores.exists():
        raise FileNotFoundError(
            f"{args.scores} not found. Run trace_scorer first."
        )

    asyncio.run(_run(args.scores, args.data_json))


if __name__ == "__main__":
    main()

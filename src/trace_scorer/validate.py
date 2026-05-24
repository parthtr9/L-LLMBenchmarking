"""Validate trace scorer V2 via Adding-Mistakes perturbation test (Lanham et al. 2023).

Two tests:
1. Adding-Mistakes: perturb top-scoring traces (wrong genes, flipped direction).
   Scorer must drop by >= 0.15 on both perturbation types.
2. Spearman correlation: re-read from trace_faithfulness_scores.json and format.

Output: outputs/validation_report.md (mirrored to public dir).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

from .consistency_checker import nli_score
from .entity_extractor import extract_gene_candidates
from .verifiers.groq_judge import GroqJudge
from .verifiers.mygene_verifier import MyGeneVerifier

logger = logging.getLogger(__name__)

_SCORES_PATH = Path("outputs/trace_faithfulness_scores.json")
_REPORT_PATH = Path("outputs/validation_report.md")
_PUBLIC_REPORT = Path(
    "LongevityBench Design System/ui_kits/longevity_bench/public/validation_report.md"
)

_FAKE_GENES = ["XYZQ1", "FAKE7", "BOGN3", "NULLP2"]
_DIRECTION_PAIRS = [
    ("extends", "shortens"), ("shortens", "extends"),
    ("increase", "decrease"), ("decrease", "increase"),
    ("increases", "decreases"), ("decreases", "increases"),
    ("increased", "decreased"), ("decreased", "increased"),
    ("upregulated", "downregulated"), ("downregulated", "upregulated"),
    ("upregulates", "downregulates"), ("downregulates", "upregulates"),
    ("longer", "shorter"), ("shorter", "longer"),
    ("elevated", "reduced"), ("reduced", "elevated"),
    ("activate", "inhibit"), ("inhibit", "activate"),
    ("activates", "inhibits"), ("inhibits", "activates"),
    ("activated", "inhibited"), ("inhibited", "activated"),
    ("promotes", "suppresses"), ("suppresses", "promotes"),
    ("promote", "suppress"), ("suppress", "promote"),
    ("enhanced", "diminished"), ("diminished", "enhanced"),
    ("pro-longevity", "anti-longevity"), ("anti-longevity", "pro-longevity"),
    ("lifespan extension", "lifespan shortening"), ("lifespan shortening", "lifespan extension"),
]


def _perturb_wrong_gene(trace: str, candidates: list[str]) -> str:
    """Replace up to 2 real gene mentions with fake genes."""
    replaced = 0
    result = trace
    for gene in candidates[:4]:
        if replaced >= 2:
            break
        fake = _FAKE_GENES[replaced % len(_FAKE_GENES)]
        new = re.sub(rf"\b{re.escape(gene)}\b", fake, result, count=1)
        if new != result:
            result = new
            replaced += 1
    return result


def _perturb_flip_direction(trace: str) -> str:
    """Swap directional keywords throughout the trace."""
    result = trace
    for src, dst in _DIRECTION_PAIRS:
        result = re.sub(rf"\b{src}\b", f"__SWAP_{dst}__", result, flags=re.IGNORECASE)
    result = re.sub(r"__SWAP_(\w+)__", r"\1", result)
    return result


async def _score_trace(
    trace: str,
    pred: str,
    fmt: str,
    mygene_verifier: MyGeneVerifier,
    groq_judge: GroqJudge,
) -> float:
    candidates = extract_gene_candidates(trace)
    gene_score = 0.0
    if candidates:
        results = await mygene_verifier.verify_batch(candidates)
        verified = sum(1 for r in results.values() if r.get("verified"))
        gene_score = verified / len(candidates)

    nli = nli_score(trace, pred, fmt)
    judgment = await groq_judge.judge_trace(trace)
    pathway_score = judgment.pathway_correctness / 5.0

    supported = [
        c for c in judgment.claims
        if c.direction != "unknown" and c.predicate != "other" and not c.negated
    ]
    refuted = [c for c in judgment.claims if c.negated]
    total = len(supported) + len(refuted)
    claim_score = len(supported) / total if total > 0 else 0.5

    return round(
        0.30 * gene_score
        + 0.20 * claim_score
        + 0.20 * nli
        + 0.30 * pathway_score,
        4,
    )


async def _run_perturbation_test(scores_data: dict) -> list[dict]:
    per_sample = scores_data.get("per_sample", [])
    top10 = sorted(per_sample, key=lambda r: r["faithfulness"], reverse=True)[:10]

    mygene_verifier = MyGeneVerifier()
    groq_judge = GroqJudge()

    rows = []
    for sample in top10:
        trace = ""
        # fetch trace from public data.json
        try:
            data = json.loads(Path(
                "LongevityBench Design System/ui_kits/longevity_bench/public/data.json"
            ).read_text())
            s = next((x for x in data["samples"] if x["id"] == sample["id"]), None)
            if s:
                cell = s.get("cells", {}).get("longevity_llm_thinking", {})
                trace = cell.get("trace") or ""
        except Exception:
            pass

        if not trace:
            continue

        pred = sample.get("pred", "A")
        fmt = sample.get("format", "mcq")
        original = sample["faithfulness"]
        candidates = extract_gene_candidates(trace)

        perturbed_gene = _perturb_wrong_gene(trace, candidates)
        perturbed_dir = _perturb_flip_direction(trace)

        score_gene = await _score_trace(perturbed_gene, pred, fmt, mygene_verifier, groq_judge)
        score_dir = await _score_trace(perturbed_dir, pred, fmt, mygene_verifier, groq_judge)

        rows.append({
            "id": sample["id"],
            "original": original,
            "wrong_gene": score_gene,
            "flipped_dir": score_dir,
            "drop_gene": round(original - score_gene, 4),
            "drop_dir": round(original - score_dir, 4),
        })
        logger.info("perturbed %s: orig=%.3f gene=%.3f dir=%.3f", sample["id"], original, score_gene, score_dir)

    mygene_verifier.save_cache()
    groq_judge.save_cache()
    return rows


def _write_report(perturb_rows: list[dict], scores_data: dict) -> None:
    spearman = scores_data.get("spearman_vs_correctness", {})
    rho = spearman.get("rho", "N/A")
    p = spearman.get("p_value", "N/A")
    ci = spearman.get("ci_95", ["N/A", "N/A"])

    mean_drop_gene = sum(r["drop_gene"] for r in perturb_rows) / len(perturb_rows) if perturb_rows else 0
    mean_drop_dir = sum(r["drop_dir"] for r in perturb_rows) / len(perturb_rows) if perturb_rows else 0
    pass_gene = "✓ PASS" if mean_drop_gene >= 0.15 else "✗ FAIL"
    pass_dir = "✓ PASS" if mean_drop_dir >= 0.15 else "✗ FAIL"

    lines = [
        "# Trace Scorer V2 — Validation Report\n",
        "## 1. Adding-Mistakes Perturbation Test (Lanham et al. 2023)\n",
        "Perturb the 10 highest-scoring traces in two ways and check faithfulness drops.\n",
        f"| Perturbation | Mean faithfulness drop | Threshold | Result |",
        f"|---|---|---|---|",
        f"| Wrong gene (XYZQ1, FAKE7) | {mean_drop_gene:.3f} | ≥ 0.15 | {pass_gene} |",
        f"| Flipped direction | {mean_drop_dir:.3f} | ≥ 0.15 | {pass_dir} |",
        "\n### Per-trace deltas\n",
        "| Sample | Original | Wrong gene | Flipped dir | Δ gene | Δ dir |",
        "|---|---|---|---|---|---|",
    ]
    for r in perturb_rows:
        lines.append(
            f"| `{r['id']}` | {r['original']:.3f} | {r['wrong_gene']:.3f} | {r['flipped_dir']:.3f} | {r['drop_gene']:+.3f} | {r['drop_dir']:+.3f} |"
        )

    lines += [
        "\n## 2. Spearman Correlation: Faithfulness vs Answer Correctness\n",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Spearman ρ | {rho} |",
        f"| p-value | {p} |",
        f"| 95% CI | [{ci[0]}, {ci[1]}] |",
        f"| n traces | {scores_data.get('n_scored', '—')} |",
        "",
        f"{'**Signal confirmed** — ρ > 0.3 and p < 0.05.' if isinstance(rho, float) and abs(rho) > 0.3 and isinstance(p, float) and p < 0.05 else '**Weak signal** — inspect Groq judge quality or increase sample size.'}",
    ]

    report = "\n".join(lines)
    _REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _REPORT_PATH.write_text(report, encoding="utf-8")
    _PUBLIC_REPORT.parent.mkdir(parents=True, exist_ok=True)
    _PUBLIC_REPORT.write_text(report, encoding="utf-8")
    logger.info("validation report → %s", _REPORT_PATH)

    print(f"\n{'─'*60}")
    print("  Validation Summary")
    print(f"{'─'*60}")
    print(f"  Wrong-gene drop:   {mean_drop_gene:.3f}  {pass_gene}")
    print(f"  Direction drop:    {mean_drop_dir:.3f}  {pass_dir}")
    print(f"  Spearman ρ:        {rho}   p={p}")
    print(f"{'─'*60}\n")


async def _run() -> None:
    if not _SCORES_PATH.exists():
        logger.error("Run trace_scorer.py first: python -m src.trace_scorer.trace_scorer")
        return

    scores_data = json.loads(_SCORES_PATH.read_text(encoding="utf-8"))
    perturb_rows = await _run_perturbation_test(scores_data)
    _write_report(perturb_rows, scores_data)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    asyncio.run(_run())


if __name__ == "__main__":
    main()

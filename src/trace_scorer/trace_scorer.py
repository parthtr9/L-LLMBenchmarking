"""Score L-LLM thinking traces — V5 (DB-anchored property check).

3-component faithfulness formula:
    faithfulness = 0.40 * gene_score
                 + 0.20 * keyword_consistency
                 + 0.40 * property_score

gene_score          — MyGene.info batch lookup across 6 species. Fraction of cited
                      gene symbols (human, mouse, rat, fly, c_elegans, yeast) that
                      exist. Multi-species extractor handles UPPER, lower-hyphen,
                      and Title-case patterns.
keyword_consistency — Directional keyword scan: trace direction matches predicted
                      label? Negation handling. 0.5 for pairwise/regression.
property_score      — CellAge v3 cross-reference. For every verified gene G, extract
                      directional claim from ±250 char window, compare against G's
                      annotated effect (Induces / Inhibits senescence). Falsifiable,
                      language-agnostic, DB-anchored. 0.5 if no annotated genes.

Replaces V4 keyword-only formula. The new property tier directly addresses the spec's
ask: "verifying that mentioned genes... exist AND have the properties claimed".

Output: outputs/trace_faithfulness_scores.json + public/trace_faithfulness_scores.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

import numpy as np
import scipy.stats

from .consistency_checker import nli_score
from .entity_extractor import extract_gene_candidates
from .property_checker import check_properties
from .verifiers.mygene_verifier import MyGeneVerifier

logger = logging.getLogger(__name__)

_DEFAULT_DATA_JSON = Path(
    "LongevityBench Design System/ui_kits/longevity_bench/public/data.json"
)
_DEFAULT_OUT = Path("outputs/trace_faithfulness_scores.json")
_PUBLIC_OUT = Path(
    "LongevityBench Design System/ui_kits/longevity_bench/public/trace_faithfulness_scores.json"
)
_THINKING_MODEL = "longevity_llm_thinking"
_MAX_CONCURRENT = 8


def _faithfulness(
    gene_score: float, nli_consistency: float, property_score: float
) -> float:
    return round(
        0.40 * gene_score + 0.20 * nli_consistency + 0.40 * property_score, 4
    )


async def _score_sample(
    sample: dict,
    mygene_verifier: MyGeneVerifier,
    gene_sem: asyncio.Semaphore,
) -> dict:
    cell = sample.get("cells", {}).get(_THINKING_MODEL, {})
    trace: str = cell.get("trace") or ""
    pred: str = (cell.get("pred") or "").strip()
    fmt: str = (sample.get("format") or "").lower()
    gold: str = (sample.get("gold") or "").strip()
    score_val = cell.get("score")
    passed: bool = cell.get("pass") or (score_val is not None and score_val >= 0.5)

    candidates = extract_gene_candidates(trace) if trace else []

    # ── Tier 1a: gene existence ─────────────────────────────────────────────
    gene_score = 0.0
    verified_genes: list[str] = []
    unverified_genes: list[str] = []
    async with gene_sem:
        if candidates:
            results = await mygene_verifier.verify_batch(candidates)
            verified_genes = [g for g, r in results.items() if r.get("verified")]
            unverified_genes = [g for g, r in results.items() if not r.get("verified")]
            gene_score = len(verified_genes) / len(candidates) if candidates else 0.0

    # ── Tier 1b: keyword consistency ────────────────────────────────────────
    kw_consistency = nli_score(trace, pred, fmt) if trace else 0.5
    consistent = kw_consistency >= 0.75

    # ── Tier 2: DB-anchored property check (CellAge directional claims) ─────
    prop = check_properties(trace, verified_genes) if trace else None
    if prop is None:
        property_score = 0.5
        n_checked = 0
        n_violated = 0
        violations: list[list[str]] = []
    else:
        property_score = prop.score
        n_checked = prop.n_checked
        n_violated = prop.n_violated
        violations = [list(v) for v in prop.violations]

    faith = _faithfulness(gene_score, kw_consistency, property_score)

    return {
        "id": sample["id"],
        "lb_id": sample.get("lb_id"),
        "format": fmt,
        "gold": gold,
        "pred": pred,
        "pass": passed,
        "trace_present": bool(trace),
        "gene_candidates": len(candidates),
        "verified_genes": verified_genes,
        "unverified_genes": unverified_genes,
        "gene_score": round(gene_score, 4),
        "nli_consistency": round(kw_consistency, 4),
        "consistent": consistent,
        "property_score": round(property_score, 4),
        "property_checked": n_checked,
        "property_violations": violations,
        "faithfulness": faith,
    }


async def _run(data_path: Path, out_path: Path) -> None:
    data = json.loads(data_path.read_text(encoding="utf-8"))

    samples_with_trace = [
        s for s in data["samples"]
        if s.get("cells", {}).get(_THINKING_MODEL, {}).get("trace")
    ]
    logger.info(
        "%d samples total, %d have %s traces",
        len(data["samples"]), len(samples_with_trace), _THINKING_MODEL,
    )
    if not samples_with_trace:
        logger.error(
            "No thinking traces found. Re-run eval with --models longevity_llm_thinking then re-export."
        )
        return

    mygene_verifier = MyGeneVerifier()
    gene_sem = asyncio.Semaphore(_MAX_CONCURRENT)

    tasks = [
        _score_sample(s, mygene_verifier, gene_sem)
        for s in samples_with_trace
    ]
    results = await asyncio.gather(*tasks)

    mygene_verifier.save_cache()

    # ── Aggregate ────────────────────────────────────────────────────────────
    n = len(results)
    avg_faith = sum(r["faithfulness"] for r in results) / n
    n_consistent = sum(1 for r in results if r["consistent"])
    total_genes = sum(r["gene_candidates"] for r in results)
    verified_total = sum(len(r["verified_genes"]) for r in results)
    avg_nli = sum(r["nli_consistency"] for r in results) / n
    avg_gene = sum(r["gene_score"] for r in results) / n
    avg_property = sum(r["property_score"] for r in results) / n
    total_property_checked = sum(r["property_checked"] for r in results)
    total_violations = sum(len(r["property_violations"]) for r in results)

    # ── Spearman faithfulness vs correctness ─────────────────────────────────
    faiths = np.array([r["faithfulness"] for r in results])
    passes = np.array([int(r["pass"]) for r in results])
    rho, p_val = scipy.stats.spearmanr(faiths, passes)

    try:
        rng = np.random.default_rng(42)
        n_boot = len(faiths)
        boot_rhos = []
        for _ in range(1000):
            idx = rng.integers(0, n_boot, size=n_boot)
            r_b, _ = scipy.stats.spearmanr(faiths[idx], passes[idx])
            if not np.isnan(r_b):
                boot_rhos.append(float(r_b))
        boot_rhos_arr = np.array(boot_rhos)
        ci_vals = [
            round(float(np.percentile(boot_rhos_arr, 2.5)), 4),
            round(float(np.percentile(boot_rhos_arr, 97.5)), 4),
        ]
    except Exception:
        ci_vals = [None, None]

    spearman_result = {
        "rho": round(float(rho), 4),
        "p_value": round(float(p_val), 4),
        "ci_95": ci_vals,
    }

    # ── Per-format breakdown ─────────────────────────────────────────────────
    faithfulness_by_format: dict = {}
    for fmt in ("mcq", "binary", "pairwise", "regression"):
        fmtr = [r for r in results if r["format"] == fmt]
        if fmtr:
            faithfulness_by_format[fmt] = {
                "n": len(fmtr),
                "avg_faithfulness": round(sum(r["faithfulness"] for r in fmtr) / len(fmtr), 4),
                "avg_accuracy": round(sum(1 for r in fmtr if r["pass"]) / len(fmtr), 4),
                "avg_gene_score": round(sum(r["gene_score"] for r in fmtr) / len(fmtr), 4),
                "avg_nli": round(sum(r["nli_consistency"] for r in fmtr) / len(fmtr), 4),
                "avg_property": round(sum(r["property_score"] for r in fmtr) / len(fmtr), 4),
            }

    summary = {
        "model": _THINKING_MODEL,
        "scorer_version": "v5",
        "formula": "0.40 * gene_score + 0.20 * keyword_consistency + 0.40 * property_score",
        "n_scored": n,
        "n_with_trace": sum(1 for r in results if r["trace_present"]),
        "avg_faithfulness": round(avg_faith, 4),
        "avg_gene_score": round(avg_gene, 4),
        "avg_nli_consistency": round(avg_nli, 4),
        "avg_property_score": round(avg_property, 4),
        "property_genes_checked": total_property_checked,
        "property_violations": total_violations,
        "n_consistent": n_consistent,
        "pct_consistent": round(n_consistent / n * 100, 1) if n else 0.0,
        "total_gene_candidates": total_genes,
        "verified_genes": verified_total,
        "pct_genes_verified": round(verified_total / total_genes * 100, 1) if total_genes else 0.0,
        "spearman_vs_correctness": spearman_result,
        "faithfulness_by_format": faithfulness_by_format,
        "per_sample": list(results),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(summary, indent=2)
    out_path.write_text(payload, encoding="utf-8")
    _PUBLIC_OUT.parent.mkdir(parents=True, exist_ok=True)
    _PUBLIC_OUT.write_text(payload, encoding="utf-8")

    # ── Print summary ────────────────────────────────────────────────────────
    print(f"\n{'─'*62}")
    print(f"  Trace Faithfulness V5 · {_THINKING_MODEL}")
    print(f"{'─'*62}")
    print(f"  Scored:            {n} traces")
    print(f"  Avg faithfulness:  {avg_faith:.3f}  (0.40×gene + 0.20×keyword + 0.40×property)")
    print(f"  Gene score:        {avg_gene:.3f}  ({verified_total}/{total_genes} verified)")
    print(f"  Keyword consist:   {avg_nli:.3f}  ({n_consistent}/{n} directionally consistent)")
    print(f"  Property score:    {avg_property:.3f}  ({total_property_checked} CellAge claims, {total_violations} violations)")
    print()
    for fmt, s in faithfulness_by_format.items():
        print(f"  {fmt:10s}  faith={s['avg_faithfulness']:.3f}  acc={s['avg_accuracy']:.3f}  gene={s['avg_gene_score']:.3f}  kw={s['avg_nli']:.3f}  n={s['n']}")
    print()
    print(f"  Spearman ρ (faithfulness vs correctness):")
    print(f"    ρ = {rho:.3f}   p = {p_val:.4f}   95% CI {ci_vals}")
    if abs(rho) > 0.3 and p_val < 0.05:
        print("    ✓ scorer is signal — ρ > 0.3, p < 0.05")
    else:
        print("    ⚠ weak signal — increase n or check keyword coverage")
    print(f"{'─'*62}\n")

    logger.info("wrote %d traces → %s", n, out_path)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-json", type=Path, default=_DEFAULT_DATA_JSON)
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    args = parser.parse_args()

    if not args.data_json.exists():
        raise FileNotFoundError(f"data.json not found: {args.data_json}")

    asyncio.run(_run(args.data_json, args.out))


if __name__ == "__main__":
    main()

"""Score L-LLM thinking traces for biological faithfulness.

Reads data.json (exported from Inspect AI logs), finds all samples that have
a thinking trace from longevity_llm_thinking, and scores each trace:

    faithfulness = 0.4 * gene_score + 0.3 * pathway_score + 0.3 * consistency

where:
  gene_score      = verified_genes / total_candidate_genes  (BioThings mygene.info)
  pathway_score   = 0.0  (reserved; set to 0 when no pathway verifier is active)
  consistency     = 1.0 if trace direction matches final answer else 0.0

Output: outputs/trace_faithfulness_scores.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

import aiohttp

from .consistency_checker import check_consistency
from .entity_extractor import extract_gene_candidates
from .verifiers.ncbi_verifier import NCBIVerifier

logger = logging.getLogger(__name__)

_DEFAULT_DATA_JSON = Path(
    "LongevityBench Design System/ui_kits/longevity_bench/public/data.json"
)
_DEFAULT_OUT = Path("outputs/trace_faithfulness_scores.json")
_PUBLIC_OUT = Path(
    "LongevityBench Design System/ui_kits/longevity_bench/public/trace_faithfulness_scores.json"
)
_THINKING_MODEL = "longevity_llm_thinking"
_MAX_CONCURRENT = 5


def _faithfulness(gene_score: float, consistent: bool) -> float:
    pathway_score = 0.0  # no pathway verifier in this build
    raw = 0.4 * gene_score + 0.3 * pathway_score + 0.3 * float(consistent)
    # Renormalise to [0,1] accounting for missing pathway component
    return round(raw / 0.7, 4)


async def _score_sample(
    sample: dict,
    verifier: NCBIVerifier,
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
) -> dict:
    cell = sample.get("cells", {}).get(_THINKING_MODEL, {})
    trace: str = cell.get("trace") or ""
    pred: str = (cell.get("pred") or "").strip()
    fmt: str = (sample.get("format") or "").lower()
    gold: str = (sample.get("gold") or "").strip()
    score_val: float | None = cell.get("score")
    passed: bool = cell.get("pass") or (score_val is not None and score_val >= 0.5)

    candidates = extract_gene_candidates(trace) if trace else []

    gene_score = 0.0
    verified_genes: list[str] = []
    unverified_genes: list[str] = []

    async with sem:
        if candidates:
            results = await verifier.verify_batch(candidates, session)
            verified_genes = [g for g, ok in results.items() if ok]
            unverified_genes = [g for g, ok in results.items() if not ok]
            gene_score = len(verified_genes) / len(candidates)

    consistent = check_consistency(trace, pred, fmt)
    faith = _faithfulness(gene_score, consistent)

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
        "pathway_score": 0.0,
        "consistent": consistent,
        "faithfulness": faith,
    }


async def _run(data_path: Path, out_path: Path) -> None:
    data = json.loads(data_path.read_text(encoding="utf-8"))

    # Filter samples that have a thinking trace
    samples_with_trace = [
        s for s in data["samples"]
        if (s.get("cells", {}).get(_THINKING_MODEL, {}).get("trace"))
    ]
    logger.info(
        "%d samples total, %d have %s traces",
        len(data["samples"]), len(samples_with_trace), _THINKING_MODEL,
    )

    if not samples_with_trace:
        logger.error(
            "No thinking traces found in data.json. "
            "Re-run eval with --models longevity_llm_thinking, then re-export."
        )
        return

    verifier = NCBIVerifier()
    sem = asyncio.Semaphore(_MAX_CONCURRENT)

    connector = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            _score_sample(s, verifier, session, sem)
            for s in samples_with_trace
        ]
        results = await asyncio.gather(*tasks)

    verifier.save_cache()

    # Aggregate
    n = len(results)
    avg_faith = sum(r["faithfulness"] for r in results) / n if n else 0.0
    n_consistent = sum(1 for r in results if r["consistent"])
    n_with_trace = sum(1 for r in results if r["trace_present"])
    total_genes = sum(r["gene_candidates"] for r in results)
    verified_total = sum(len(r["verified_genes"]) for r in results)

    summary = {
        "model": _THINKING_MODEL,
        "n_scored": n,
        "n_with_trace": n_with_trace,
        "avg_faithfulness": round(avg_faith, 4),
        "n_consistent": n_consistent,
        "pct_consistent": round(n_consistent / n * 100, 1) if n else 0.0,
        "total_gene_candidates": total_genes,
        "verified_genes": verified_total,
        "pct_genes_verified": round(verified_total / total_genes * 100, 1) if total_genes else 0.0,
        "faithfulness_by_format": {},
        "per_sample": results,
    }

    for fmt in ("mcq", "binary", "pairwise"):
        fmt_results = [r for r in results if r["format"] == fmt]
        if fmt_results:
            summary["faithfulness_by_format"][fmt] = {
                "n": len(fmt_results),
                "avg_faithfulness": round(
                    sum(r["faithfulness"] for r in fmt_results) / len(fmt_results), 4
                ),
                "avg_accuracy": round(
                    sum(1 for r in fmt_results if r["pass"]) / len(fmt_results), 4
                ),
            }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(summary, indent=2)
    out_path.write_text(payload, encoding="utf-8")
    _PUBLIC_OUT.parent.mkdir(parents=True, exist_ok=True)
    _PUBLIC_OUT.write_text(payload, encoding="utf-8")
    logger.info(
        "scored %d traces → avg_faithfulness=%.3f consistent=%d/%d → %s",
        n, avg_faith, n_consistent, n, out_path,
    )

    # Print summary table
    print(f"\n{'─'*60}")
    print(f"  Trace faithfulness · {_THINKING_MODEL}")
    print(f"{'─'*60}")
    print(f"  Scored:           {n} traces")
    print(f"  Avg faithfulness: {avg_faith:.3f}")
    print(f"  Consistent:       {n_consistent}/{n} ({n_consistent/n*100:.1f}%)")
    print(f"  Genes verified:   {verified_total}/{total_genes}")
    print()
    for fmt, s in summary["faithfulness_by_format"].items():
        print(f"  {fmt:10s}  faith={s['avg_faithfulness']:.3f}  acc={s['avg_accuracy']:.3f}  n={s['n']}")
    print(f"{'─'*60}\n")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-json", type=Path, default=_DEFAULT_DATA_JSON,
        help="Path to dashboard data.json"
    )
    parser.add_argument(
        "--out", type=Path, default=_DEFAULT_OUT,
        help="Output path for trace_faithfulness_scores.json"
    )
    args = parser.parse_args()

    if not args.data_json.exists():
        raise FileNotFoundError(f"data.json not found: {args.data_json}")

    asyncio.run(_run(args.data_json, args.out))


if __name__ == "__main__":
    main()

"""Run multi-species extractor + mygene + property checker on smoke traces."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from inspect_ai.log import read_eval_log

from src.trace_scorer.entity_extractor import extract_gene_candidates
from src.trace_scorer.property_checker import check_properties
from src.trace_scorer.verifiers.mygene_verifier import MyGeneVerifier

logger = logging.getLogger(__name__)
_LOG_DIR = Path("outputs/inspect/longevity_llm_thinking")


def _latest_log() -> Path:
    logs = sorted(_LOG_DIR.glob("*.eval"), key=lambda p: p.stat().st_mtime, reverse=True)
    return logs[0]


async def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")

    log_path = _latest_log()
    print(f"log: {log_path.name}\n")
    log = read_eval_log(str(log_path))
    samples = list(log.samples)[-5:]

    verifier = MyGeneVerifier()

    print(f"{'lb_id':<18s} {'fmt':<10s} cand verified property_score violations")
    print("─" * 100)
    for s in samples:
        md = s.metadata or {}
        lb_id = md.get("lb_id", "?")
        fmt = md.get("format", "?")
        trace = md.get("reasoning") or ""
        if not trace:
            print(f"{lb_id:<18s} {fmt:<10s} (no trace)")
            continue

        candidates = extract_gene_candidates(trace)
        verify = await verifier.verify_batch(candidates)
        verified = [g for g, r in verify.items() if r.get("verified")]
        prop = check_properties(trace, verified)
        v_str = ", ".join(f"{g}:{c}!={d}" for g, c, d in prop.violations) or "—"
        print(f"{lb_id:<18s} {fmt:<10s} {len(candidates):>4d} {len(verified):>7d}    "
              f"{prop.score:>4.2f} ({prop.n_correct}/{prop.n_checked})    {v_str}")

    verifier.save_cache()


if __name__ == "__main__":
    asyncio.run(main())

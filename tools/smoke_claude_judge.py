"""Run Claude judge on the 5 smoke-test thinking traces.

Reads the most recent longevity_llm_thinking .eval log produced by the smoke run,
extracts trace + pred + gold per sample, sends each to ClaudeJudge, prints scores.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv
from inspect_ai.log import read_eval_log, list_eval_logs

from src.trace_scorer.verifiers.claude_judge import ClaudeJudge

logger = logging.getLogger(__name__)

_LOG_DIR = Path("outputs/inspect/longevity_llm_thinking")


def _latest_log() -> Path:
    logs = sorted(_LOG_DIR.glob("*.eval"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs:
        raise FileNotFoundError(f"no .eval logs in {_LOG_DIR}")
    return logs[0]


async def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    log_path = _latest_log()
    print(f"Using log: {log_path.name}\n")
    log = read_eval_log(str(log_path))

    judge = ClaudeJudge()

    # Take last 5 samples to match the 5-row smoke run; if more, the latest 5.
    samples = list(log.samples)[-5:]

    print(f"{'lb_id':<18s} {'fmt':<10s} {'pred':<6s} {'gold':<6s} pathway claim  evid  acc")
    print("─" * 90)
    for sample in samples:
        md = sample.metadata or {}
        lb_id = md.get("lb_id", "?")
        fmt = md.get("format", "?")
        trace = md.get("reasoning") or ""
        pred = (sample.output.completion or "").strip()
        gold = ""
        # Inspect AI puts the gold answer in sample.target
        if sample.target:
            gold = str(sample.target).strip()
        score_val = None
        if sample.scores:
            first = next(iter(sample.scores.values()))
            score_val = first.value

        if not trace:
            print(f"{lb_id:<18s} {fmt:<10s} {pred[:5]:<6s} {gold[:5]:<6s} (no trace)")
            continue

        judgment = await judge.judge(trace, pred, gold, fmt)
        pw = ClaudeJudge.pathway_score(judgment)
        cs = ClaudeJudge.claim_score(judgment)
        ev = ClaudeJudge.evidence_score(judgment)
        acc = score_val if score_val is not None else "?"
        print(
            f"{lb_id:<18s} {fmt:<10s} {pred[:5]:<6s} {gold[:5]:<6s} "
            f"{pw:>5.2f}  {cs:>5.2f}  {ev:>5.2f}  {acc}"
        )
        print(f"    claims: {[(c.entity, c.direction, c.negated) for c in judgment.claims]}")
        print(f"    judge says: {judgment.reasoning[:200]}")
        print()

    judge.save_cache()


if __name__ == "__main__":
    asyncio.run(main())

"""Extract LLM predictions from Inspect .eval logs into a flat JSON cache.

Reads every .eval file under outputs/inspect/<model>/ for non-baseline models
and writes outputs/prediction_cache.json keyed by "<model_name>::<lb_id>".

The litellm_solver checks this cache before making API calls, so re-running an
eval on a parquet that was already evaluated hits the cache instead of the API.

Usage:
    .venv/bin/python -m tools.cache_predictions
    .venv/bin/python -m tools.cache_predictions --log-dir outputs/inspect --out outputs/prediction_cache.json
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from inspect_ai.log import EvalLog, read_eval_log, list_eval_logs

logger = logging.getLogger(__name__)

_BASELINE_MODELS = {"majority_baseline", "random_baseline"}

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_LOG_DIR = _ROOT / "outputs" / "inspect"
_DEFAULT_OUT = _ROOT / "outputs" / "prediction_cache.json"


def _extract_pred(sample) -> str | None:
    if sample.output and sample.output.completion:
        return sample.output.completion.strip()
    return None


def _extract_score(sample) -> tuple[float | None, bool | None]:
    if not sample.scores:
        return None, None
    first = next(iter(sample.scores.values()))
    v = first.value
    if v is None:
        return None, None
    if isinstance(v, bool):
        return (1.0 if v else 0.0), v
    if isinstance(v, (int, float)):
        return float(v), float(v) >= 0.5
    return None, None


def _extract_tokens(sample) -> int | None:
    if sample.output and sample.output.usage:
        return (sample.output.usage.total_tokens
                or sample.output.usage.output_tokens)
    return None


def _extract_latency(sample) -> float | None:
    if sample.metadata and sample.metadata.get("latency_s") is not None:
        return sample.metadata["latency_s"]
    return None


def _extract_trace(sample) -> str | None:
    if sample.output and sample.output.message:
        msg = sample.output.message
        r = getattr(msg, "reasoning_content", None)
        if not r and sample.metadata:
            r = sample.metadata.get("reasoning")
        return r or None
    return None


def build_cache(log_dir: Path) -> dict[str, dict]:
    """Walk all .eval logs and return flat dict keyed '<model>::<lb_id>'."""
    entries: dict[str, dict] = {}
    skipped_runs = 0
    cached_samples = 0

    for log_info in list_eval_logs(str(log_dir), recursive=True):
        log: EvalLog = read_eval_log(log_info)

        model_name = (log.eval.task_args or {}).get(
            "model_name",
            (log.eval.model or "unknown").split("/")[-1],
        )

        if model_name in _BASELINE_MODELS:
            logger.debug("skipping baseline: %s", model_name)
            skipped_runs += 1
            continue

        if not log.samples:
            logger.warning("no samples in log: %s", log_info.name)
            continue

        for sample in log.samples:
            # lb_id stored in metadata by parquet_task._row_to_sample
            lb_id = (sample.metadata or {}).get("lb_id")
            if not lb_id:
                # Fall back: sample id format is "{lb_id}_{index:05d}"
                raw_id = str(sample.id or "")
                lb_id = raw_id[:-6] if len(raw_id) > 6 and raw_id[-6] == "_" else raw_id

            if not lb_id:
                logger.warning("could not determine lb_id for sample %s", sample.id)
                continue

            key = f"{model_name}::{lb_id}"
            score, passed = _extract_score(sample)

            entries[key] = {
                "model_name": model_name,
                "lb_id": lb_id,
                "pred": _extract_pred(sample),
                "score": score,
                "pass": passed,
                "latency_s": _extract_latency(sample),
                "tokens": _extract_tokens(sample),
                "trace": _extract_trace(sample),
                "format": (sample.metadata or {}).get("format"),
            }
            cached_samples += 1

        logger.info("cached %d samples from model=%s", len(log.samples), model_name)

    logger.info(
        "total: %d entries cached, %d baseline runs skipped",
        cached_samples, skipped_runs,
    )
    return entries


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--log-dir", type=Path, default=_DEFAULT_LOG_DIR,
        help="Root directory containing per-model .eval subdirs",
    )
    parser.add_argument(
        "--out", type=Path, default=_DEFAULT_OUT,
        help="Output JSON cache path",
    )
    args = parser.parse_args()

    if not args.log_dir.exists():
        logger.error("log-dir does not exist: %s", args.log_dir)
        return

    entries = build_cache(args.log_dir)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_entries": len(entries),
        "entries": entries,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("cache written → %s  (%d entries)", args.out, len(entries))

    # Print summary by model
    by_model: dict[str, int] = {}
    for v in entries.values():
        m = v["model_name"]
        by_model[m] = by_model.get(m, 0) + 1
    print("\n=== Prediction cache summary ===")
    for model, count in sorted(by_model.items()):
        print(f"  {model:<30s} {count:4d} samples")
    print(f"\n  Total: {len(entries)} entries → {args.out}")


if __name__ == "__main__":
    main()

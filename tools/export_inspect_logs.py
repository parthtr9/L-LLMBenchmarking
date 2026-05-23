"""Export Inspect AI .eval logs → JSON for the LongevityBench dashboard.

This is a READ-ONLY bridge. It does NOT touch Inspect AI internals.
It reads logs written by `run_inspect.py` and emits a normalised JSON
shape the static dashboard (design-system/ui_kits/longevity_bench/)
consumes via fetch().

Usage:
    python -m tools.export_inspect_logs \\
        --log-dir outputs/inspect \\
        --out design-system/ui_kits/longevity_bench/public/data.json

Run after every Inspect AI eval. The dashboard then loads
`./public/data.json` on page load — no backend needed.

Output schema (single JSON file):
{
  "generated_at": "2026-05-23T15:04:00Z",
  "models": [
    {"id": "longevity_llm", "name": "L-LLM", "color": "#4ca045"}
  ],
  "tasks": [
    {"id": "LB-0038", "name": "epistasis_ternary", "format": "ternary",
     "n": 200, "metric": "macro_f1"}
  ],
  "runs": [
    {"id": "<inspect-eval-id>", "model": "longevity_llm",
     "lb_id": "LB-0038", "status": "complete", "n": 200, "completed": 200,
     "errors": 0, "started": "...", "duration_s": 612,
     "scores": {"macro_f1": 0.62, "balanced_accuracy": 0.59},
     "ci_95": [0.58, 0.66]}
  ],
  "samples": [
    {"id": "LB-0038_00003", "lb_id": "LB-0038", "format": "ternary",
     "metadata": {...}, "gold": "synergistic",
     "cells": {
       "longevity_llm": {"pred": "synergistic", "score": 1.0, "pass": true,
                         "latency_s": 4.2, "tokens": 384,
                         "trace": "...", "reasoning_present": true}
     }}
  ],
  "trace_scores": {
    "longevity_llm": {
      "avg_faithfulness": 0.81,
      "consistent": 187, "total": 190,
      "entities_by_source": {
        "wormbase": {"verified": 487, "total": 512},
        "ncbi":     {"verified": 312, "total": 318}
      }
    }
  }
}
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Inspect AI's log-reading API. This is the public API; we never reach
# into private modules. See https://inspect.aisi.org.uk for the spec.
from inspect_ai.log import EvalLog, list_eval_logs, read_eval_log

logger = logging.getLogger(__name__)

# Model display config — mirrors design-system colors. Add new entries
# whenever you register a new model in config/models.yaml.
MODEL_DISPLAY = {
    "longevity_llm":          {"name": "L-LLM",        "color": "#4ca045"},
    "longevity_llm_thinking": {"name": "L-LLM (think)","color": "#3d8838"},
    "gemini_flash":           {"name": "Gemini Flash", "color": "#1f9bd6"},
    "deepseek_chat":          {"name": "DeepSeek",     "color": "#6b3fa0"},
    "claude_sonnet":          {"name": "Claude 4.5",   "color": "#c98b1c"},
    "majority_baseline":      {"name": "Majority",     "color": "#8c948c"},
    "random_baseline":        {"name": "Random",       "color": "#b3b8b3"},
}


def _model_meta(model_id: str) -> dict[str, str]:
    base = MODEL_DISPLAY.get(model_id, {"name": model_id, "color": "#8c948c"})
    return {"id": model_id, **base}


def _extract_score(log: EvalLog) -> dict[str, Any]:
    """Pull aggregate score values + CIs out of an Inspect EvalLog."""
    out: dict[str, Any] = {}
    if not log.results or not log.results.scores:
        return out
    for s in log.results.scores:
        for metric_name, m in s.metrics.items():
            out[metric_name] = round(m.value, 4)
    return out


def _extract_cell(sample: Any) -> dict[str, Any]:
    """Pull a single (sample × model) cell's pred / pass / score / trace."""
    cell: dict[str, Any] = {
        "pred": None, "score": None, "pass": None,
        "latency_s": None, "tokens": None,
        "trace": None, "reasoning_present": False,
    }
    # Model output
    if sample.output and sample.output.completion:
        cell["pred"] = sample.output.completion.strip()
    # Token usage
    if sample.output and sample.output.usage:
        cell["tokens"] = (sample.output.usage.total_tokens
                          or sample.output.usage.output_tokens)
    # Score (Inspect stores per-scorer; we take the first one)
    if sample.scores:
        first = next(iter(sample.scores.values()))
        if first.value is not None:
            v = first.value
            if isinstance(v, bool):
                cell["score"] = 1.0 if v else 0.0
                cell["pass"] = v
            elif isinstance(v, (int, float)):
                cell["score"] = float(v)
                cell["pass"] = float(v) >= 0.5
            else:
                cell["pred"] = str(v)
    # latency stored in metadata by litellm_solver
    if sample.metadata and sample.metadata.get("latency_s") is not None:
        cell["latency_s"] = sample.metadata["latency_s"]
    # Reasoning trace: native reasoning_content first, then metadata fallback.
    # litellm_solver extracts <think> blocks and stores them in state.metadata["reasoning"].
    if sample.output and sample.output.message:
        msg = sample.output.message
        reasoning = getattr(msg, "reasoning_content", None)
        if not reasoning and sample.metadata:
            reasoning = sample.metadata.get("reasoning")
        if reasoning:
            cell["trace"] = reasoning
            cell["reasoning_present"] = True
    return cell


def _gather(log_dir: Path) -> dict[str, Any]:
    """Walk every Inspect log under log_dir; group by sample.id."""
    models: dict[str, dict] = {}
    tasks: dict[str, dict] = {}
    runs: list[dict] = []
    samples: dict[str, dict] = {}  # keyed by sample.id

    # Inspect AI: list_eval_logs returns a list of EvalLogInfo
    for log_info in list_eval_logs(str(log_dir), recursive=True):
        log: EvalLog = read_eval_log(log_info)
        model_id = (log.eval.task_args or {}).get(
            "model_name",
            (log.eval.model or "unknown").split("/")[-1],
        )
        if model_id not in models:
            models[model_id] = _model_meta(model_id)

        lb_id = (log.eval.task_args or {}).get("lb_id", "unknown")
        if lb_id not in tasks:
            tasks[lb_id] = {"id": lb_id, "name": lb_id, "format": None,
                            "n": 0, "metric": None}

        runs.append({
            "id": log.eval.eval_id,
            "model": model_id,
            "lb_id": lb_id,
            "status": log.status or "complete",
            "n": len(log.samples) if log.samples else 0,
            "completed": len(log.samples) if log.samples else 0,
            "errors": 0,
            "started": log.eval.created or "",
            "duration_s": None,
            "scores": _extract_score(log),
            "ci_95": None,
        })

        for sample in (log.samples or []):
            sid = sample.id
            if sid not in samples:
                samples[sid] = {
                    "id": sid,
                    "lb_id": lb_id,
                    "format": (sample.metadata or {}).get("format"),
                    "metadata": sample.metadata or {},
                    "gold": str(sample.target).strip() if sample.target else None,
                    "cells": {},
                }
            samples[sid]["cells"][model_id] = _extract_cell(sample)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "models": list(models.values()),
        "tasks": list(tasks.values()),
        "runs": runs,
        "samples": list(samples.values()),
        "trace_scores": {},  # populated by a separate trace-scoring step
    }


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-dir", type=Path, default=Path("outputs/inspect"),
                        help="Directory containing Inspect AI .eval logs.")
    parser.add_argument("--out", type=Path,
                        default=Path("design-system/ui_kits/longevity_bench/public/data.json"),
                        help="Where to write the dashboard JSON.")
    args = parser.parse_args()

    if not args.log_dir.exists():
        logger.error("log dir not found: %s", args.log_dir)
        logger.error("run an eval first: python -m src.eval.run_inspect --lb-id LB-0038 --limit 20")
        sys.exit(1)

    bundle = _gather(args.log_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(bundle, indent=2, default=str), encoding="utf-8")
    logger.info("wrote %d samples, %d runs across %d models → %s",
                len(bundle["samples"]), len(bundle["runs"]),
                len(bundle["models"]), args.out)


if __name__ == "__main__":
    main()

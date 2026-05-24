"""CLI: run any parquet benchmark with Inspect AI + LiteLLM."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from inspect_ai import eval as inspect_eval

from .inspect_tasks.parquet_task import parquet_task

logger = logging.getLogger(__name__)

_DEFAULT_MODELS_YAML = (
    Path(__file__).resolve().parent.parent.parent / "config" / "models.yaml"
)


def _load_registry(path: Path) -> dict:
    with open(path) as fh:
        return yaml.safe_load(fh)["models"]


def _print_mae_summary(logs: list) -> None:
    for log in logs:
        if not log.samples:
            continue
        maes = []
        for sample in log.samples:
            if sample.scores:
                for score in sample.scores.values():
                    meta = score.metadata or {}
                    if "mae" in meta and meta["mae"] is not None:
                        maes.append(meta["mae"])
        if maes:
            logger.info("raw MAE (n=%d): %.4f", len(maes), sum(maes) / len(maes))


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="Run any parquet benchmark eval.")
    parser.add_argument("--parquet", required=True,
                        help="Path to the parquet benchmark file.")
    parser.add_argument("--fmt-filter", default=None,
                        help="Restrict to one format value (mcq / binary / regression / etc).")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max samples per model. Default: all.")
    parser.add_argument("--models", default="longevity_llm",
                        help="Comma-separated model names from config/models.yaml.")
    parser.add_argument("--models-yaml", type=Path, default=_DEFAULT_MODELS_YAML)
    parser.add_argument("--log-dir", type=Path, default=Path("outputs/inspect"))
    parser.add_argument("--max-tokens", type=int, default=500)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    parquet_path = Path(args.parquet).resolve()
    if not parquet_path.exists():
        logger.error("parquet not found: %s", parquet_path)
        sys.exit(1)

    registry = _load_registry(args.models_yaml)
    model_names = [m.strip() for m in args.models.split(",") if m.strip()]

    for model_name in model_names:
        if model_name not in registry:
            logger.error("unknown model %r — available: %s", model_name, list(registry.keys()))
            sys.exit(1)

    args.log_dir.mkdir(parents=True, exist_ok=True)

    for model_name in model_names:
        model_cfg = registry[model_name]

        # Health-check vLLM endpoints (L-LLM)
        api_base_env = model_cfg.get("api_base_env")
        if api_base_env:
            api_base = os.getenv(api_base_env)
            if not api_base:
                logger.error("model %s requires %s to be set", model_name, api_base_env)
                sys.exit(1)

        log_subdir = args.log_dir / model_name
        log_subdir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "running model=%s parquet=%s fmt=%s limit=%s dry_run=%s",
            model_name, parquet_path.name, args.fmt_filter, args.limit, args.dry_run,
        )

        t = parquet_task(
            parquet_path=str(parquet_path),
            model_name=model_name,
            fmt_filter=args.fmt_filter,
            limit=args.limit,
            dry_run=args.dry_run,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            seed=args.seed,
        )

        logs = inspect_eval(t, model="none", log_dir=str(log_subdir))

        for log in logs:
            if log.results:
                for score in log.results.scores:
                    logger.info(
                        "model=%s scorer=%s metrics=%s",
                        model_name, score.name,
                        {k: round(v.value, 4) for k, v in score.metrics.items()},
                    )
        _print_mae_summary(logs)
        logger.info("logs saved → %s", log_subdir)


if __name__ == "__main__":
    main()

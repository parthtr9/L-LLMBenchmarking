"""CLI: run LongeBench tasks with Inspect AI + LiteLLM across multiple providers."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml
from dotenv import load_dotenv
from inspect_ai import eval as inspect_eval

from .inspect_tasks.longebench import longebench_task

logger = logging.getLogger(__name__)

_DEFAULT_MODELS_YAML = (
    Path(__file__).resolve().parent.parent.parent / "config" / "models.yaml"
)


def _load_registry(path: Path) -> dict:
    with open(path) as fh:
        return yaml.safe_load(fh)["models"]


def _http_get_json(url: str, headers: dict[str, str]) -> Any:
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except HTTPError as exc:
        raise RuntimeError(
            f"HTTP {exc.code} from {url}: {exc.read().decode('utf-8', 'ignore')}"
        )
    except URLError as exc:
        raise RuntimeError(f"unable to reach {url}: {exc}")


def _check_hf_health(api_base: str, token: str | None) -> None:
    health_url = api_base.rstrip("/") + "/health"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        with urlopen(Request(health_url, headers=headers), timeout=20) as resp:
            if resp.status != 200:
                raise RuntimeError(f"health check failed: {resp.status}")
    except HTTPError as exc:
        raise RuntimeError(
            f"health check failed: {exc.code} {exc.reason} - {exc.read().decode('utf-8', 'ignore')}"
        )
    except URLError as exc:
        raise RuntimeError(f"health check failed: {exc}")


def _list_hf_models(api_base: str, token: str | None) -> list[str]:
    model_url = api_base.rstrip("/") + "/v1/models"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    payload = _http_get_json(model_url, headers)
    if isinstance(payload, dict):
        if "data" in payload and isinstance(payload["data"], list):
            return [item.get("id") for item in payload["data"] if isinstance(item, dict) and "id" in item]
        if "models" in payload and isinstance(payload["models"], list):
            return [item.get("id") for item in payload["models"] if isinstance(item, dict) and "id" in item]
    raise RuntimeError(f"unexpected /v1/models payload: {payload}")


def _assert_hf_model_available(api_base: str, token: str | None, model_name: str) -> None:
    available = _list_hf_models(api_base, token)
    if model_name in available:
        return
    raise RuntimeError(
        f"configured model '{model_name}' not found on endpoint. "
        f"Available models: {available}"
    )


def _print_mae_summary(logs: list) -> None:
    """Extract and log raw MAE from sample scores for regression tasks."""
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
            mean_mae = sum(maes) / len(maes)
            logger.info("raw MAE (n=%d): %.4f", len(maes), mean_mae)


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Run LongeBench with Inspect AI + LiteLLM."
    )
    parser.add_argument("--task", default="longebench", choices=["longebench"])
    parser.add_argument("--lb-id", default="LB-0038", help="LongeBench task id.")
    parser.add_argument("--split", default="eval")
    parser.add_argument("--dataset-config", default="benchmark", choices=["benchmark", "extra"])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--models",
        default="longevity_llm",
        help="Comma-separated model names from config/models.yaml.",
    )
    parser.add_argument("--models-yaml", type=Path, default=_DEFAULT_MODELS_YAML)
    parser.add_argument("--log-dir", type=Path, default=Path("outputs/inspect"))
    parser.add_argument("--max-tokens", type=int, default=500)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load/build samples without making model calls.",
    )
    args = parser.parse_args()

    registry = _load_registry(args.models_yaml)
    model_names = [m.strip() for m in args.models.split(",") if m.strip()]

    for model_name in model_names:
        if model_name not in registry:
            logger.error(
                "unknown model %r — available: %s", model_name, list(registry.keys())
            )
            sys.exit(1)

    args.log_dir.mkdir(parents=True, exist_ok=True)

    for model_name in model_names:
        model_cfg = registry[model_name]
        api_base_env = model_cfg.get("api_base_env")
        api_key_env = model_cfg.get("api_key_env")
        if api_base_env:
            api_base = os.getenv(api_base_env)
            api_key = os.getenv(api_key_env) if api_key_env else None
            if not api_base:
                logger.error(
                    "model %s requires %s to be set", model_name, api_base_env
                )
                sys.exit(1)
            try:
                _check_hf_health(api_base, api_key)
            except RuntimeError as exc:
                logger.error(
                    "HF endpoint validation failed for model %s: %s",
                    model_name,
                    exc,
                )
                sys.exit(1)

            litellm_model = model_cfg.get("litellm_model", "")
            if litellm_model.startswith("openai/"):
                configured_model = litellm_model.split("/", 1)[1]
                try:
                    _assert_hf_model_available(api_base, api_key, configured_model)
                except RuntimeError as exc:
                    logger.error(
                        "HF model discovery failed for model %s: %s",
                        model_name,
                        exc,
                    )
                    sys.exit(1)

        log_subdir = args.log_dir / model_name
        log_subdir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "running lb_id=%s model=%s limit=%s dry_run=%s",
            args.lb_id,
            model_name,
            args.limit,
            args.dry_run,
        )

        t = longebench_task(
            lb_id=args.lb_id,
            split=args.split,
            limit=args.limit,
            model_name=model_name,
            dataset_config=args.dataset_config,
            dry_run=args.dry_run,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            seed=args.seed,
        )

        logs = inspect_eval(
            t,
            model="none",
            log_dir=str(log_subdir),
        )

        for log in logs:
            if log.results:
                for score in log.results.scores:
                    logger.info(
                        "model=%s scorer=%s metrics=%s",
                        model_name,
                        score.name,
                        {k: round(v.value, 4) for k, v in score.metrics.items()},
                    )
        _print_mae_summary(logs)
        logger.info("logs saved → %s", log_subdir)
        logger.info("view with: inspect view %s", log_subdir)


if __name__ == "__main__":
    main()

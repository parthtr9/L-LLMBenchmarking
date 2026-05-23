"""Inspect AI task definition for insilicomedicine/longebench."""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from datasets import load_dataset
from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import (
    ChatMessageAssistant,
    ChatMessageSystem,
    ChatMessageUser,
)

from ..inspect_scorers import longebench_scorer
from ..inspect_solvers import (
    litellm_solver,
    majority_baseline_solver,
    random_baseline_solver,
)

logger = logging.getLogger(__name__)

_MODELS_YAML = (
    Path(__file__).resolve().parent.parent.parent.parent / "config" / "models.yaml"
)
_HF_CACHE = Path("data/cache/huggingface")


def _load_model_cfg(model_name: str) -> dict[str, Any]:
    with open(_MODELS_YAML) as fh:
        return yaml.safe_load(fh)["models"][model_name]


def _ensure_messages(value: Any) -> list[dict[str, str]]:
    if isinstance(value, str):
        value = json.loads(value)
    return [dict(m) for m in value]


def _to_inspect_message(msg: dict[str, str]) -> Any:
    role = msg["role"]
    content = msg["content"]
    if role == "system":
        return ChatMessageSystem(content=content)
    if role == "assistant":
        return ChatMessageAssistant(content=content)
    return ChatMessageUser(content=content)


def _row_to_sample(row: dict[str, Any], index: int) -> Sample:
    messages = _ensure_messages(row["messages"])
    input_msgs = [_to_inspect_message(m) for m in messages[:-1]]
    target = str(messages[-1]["content"]).strip()
    lb_id = row.get("lb_id", "")
    return Sample(
        input=input_msgs,
        target=target,
        id=f"{lb_id}_{index:05d}",
        metadata={
            "lb_id": row.get("lb_id"),
            "display_name": row.get("display_name"),
            "format": row.get("format"),
            "metric": row.get("metric"),
            "domain": row.get("domain"),
            "units": row.get("units"),
        },
    )


def _load_hf_samples(
    lb_id: str | None,
    split: str,
    limit: int | None,
    config_name: str,
) -> list[Sample]:
    hf_token = os.getenv("HF_TOKEN")
    dataset = load_dataset(
        "insilicomedicine/longebench",
        config_name,
        split=split,
        cache_dir=str(_HF_CACHE),
        token=hf_token,
    )
    if lb_id:
        dataset = dataset.filter(lambda r: r["lb_id"] == lb_id)
    if limit is not None:
        dataset = dataset.select(range(min(limit, len(dataset))))
    samples = [_row_to_sample(dict(row), i) for i, row in enumerate(dataset)]
    logger.info(
        "loaded %d samples lb_id=%s split=%s config=%s",
        len(samples),
        lb_id,
        split,
        config_name,
    )
    return samples


@task
def longebench_task(
    lb_id: str = "LB-0038",
    split: str = "eval",
    limit: int | None = None,
    model_name: str = "longevity_llm",
    dataset_config: str = "benchmark",
    dry_run: bool = False,
    max_tokens: int = 500,
    temperature: float = 0.0,
    seed: int = 42,
) -> Task:
    """LongeBench evaluation task.

    Args:
        lb_id: LongeBench task id to filter on (e.g. 'LB-0038'). Empty string runs all.
        split: Dataset split ('eval').
        limit: Max samples to run. None = all.
        model_name: Key in config/models.yaml.
        dataset_config: HF dataset config name ('benchmark' or 'extra').
        dry_run: Skip model calls; outputs '__dry_run__' placeholder.
        max_tokens: Max output tokens per call.
        temperature: Sampling temperature.
        seed: Reproducibility seed.
    """
    model_cfg = _load_model_cfg(model_name)
    samples = _load_hf_samples(lb_id or None, split, limit, dataset_config)

    baseline_type = model_cfg.get("type") == "baseline"
    strategy = model_cfg.get("strategy", "")

    if baseline_type and strategy == "random":
        slvr = random_baseline_solver(seed=seed)
    elif baseline_type and strategy == "majority":
        targets = [s.target for s in samples]
        majority_label = Counter(targets).most_common(1)[0][0] if targets else ""
        slvr = majority_baseline_solver(majority_label=majority_label)
    else:
        slvr = litellm_solver(
            model_cfg=model_cfg,
            dry_run=dry_run,
            max_tokens=max_tokens,
            temperature=temperature,
            seed=seed,
        )

    return Task(
        dataset=samples,
        solver=slvr,
        scorer=longebench_scorer(),
    )

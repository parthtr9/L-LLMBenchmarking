"""Generic Inspect AI task that loads from any local parquet file.

Parquet must have columns: lb_id, format, metric, messages, units, domain, display_name.
messages column: JSON string or list of {role, content} dicts.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
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


_FORMAT_INSTRUCTIONS: dict[str, str] = {
    "mcq":        "\n\nAnswer with only the single letter of your choice (A, B, C, or D). No explanation.",
    "binary":     "\n\nAnswer with only A or B. No explanation.",
    "pairwise":   "\n\nAnswer with only A or B. No explanation.",
    "ternary":    "\n\nAnswer with only the label (e.g. synergistic, antagonistic, additive). No explanation.",
    "regression": "\n\nAnswer with only a single integer. No units, no explanation.",
}


def _row_to_sample(row: dict[str, Any], index: int) -> Sample:
    messages = _ensure_messages(row["messages"])
    fmt = str(row.get("format") or "").lower()
    instruction = _FORMAT_INSTRUCTIONS.get(fmt, "")

    # Append concise-answer instruction to system message so model stays under token limit.
    processed: list[dict[str, str]] = []
    for i, m in enumerate(messages[:-1]):
        if i == 0 and m.get("role") == "system" and instruction:
            processed.append({"role": "system", "content": m["content"] + instruction})
        else:
            processed.append(m)

    input_msgs = [_to_inspect_message(m) for m in processed]
    target = str(messages[-1]["content"]).strip()
    lb_id = row.get("lb_id", f"row_{index:05d}")
    return Sample(
        input=input_msgs,
        target=target,
        id=f"{lb_id}_{index:05d}",
        metadata={
            "lb_id": row.get("lb_id"),
            "display_name": row.get("display_name"),
            "display_group": row.get("display_group"),
            "format": row.get("format"),
            "metric": row.get("metric"),
            "domain": row.get("domain"),
            "units": row.get("units"),
        },
    )


def _compute_fmt_majority(test_path: Path, test_samples: list[Sample]) -> dict[str, str]:
    """Compute per-format majority label from the training split (if available).

    Falls back to test samples when no train file found.
    Supported formats: mcq, binary, pairwise.
    """
    train_path = Path(str(test_path).replace("_test.parquet", "_train.parquet"))
    if not train_path.exists():
        train_path = None

    fmt_majority: dict[str, str] = {}

    def _get_target(msgs_val: Any) -> str:
        msgs = _ensure_messages(msgs_val)
        return str(msgs[-1]["content"]).strip()

    for fmt in ("mcq", "binary", "pairwise"):
        if train_path:
            df = pd.read_parquet(train_path)
            rows = df[df["format"] == fmt] if "format" in df.columns else pd.DataFrame()
        else:
            rows = pd.DataFrame()

        if rows.empty:
            fmt_targets = [s.target for s in test_samples
                           if (s.metadata or {}).get("format") == fmt]
        else:
            fmt_targets = rows["messages"].apply(_get_target).tolist()

        if not fmt_targets:
            continue
        fmt_majority[fmt] = Counter(fmt_targets).most_common(1)[0][0]

    fmt_majority.setdefault("default", "A")
    logger.info("majority baseline labels: %s", fmt_majority)
    return fmt_majority


def load_parquet_samples(
    parquet_path: Path,
    limit: int | None = None,
    fmt_filter: str | None = None,
) -> list[Sample]:
    df = pd.read_parquet(parquet_path)
    if fmt_filter:
        df = df[df["format"] == fmt_filter]
    if limit is not None:
        df = df.head(limit)
    samples = [_row_to_sample(row.to_dict(), i) for i, (_, row) in enumerate(df.iterrows())]
    logger.info(
        "loaded %d samples from %s (fmt=%s limit=%s)",
        len(samples), parquet_path.name, fmt_filter, limit,
    )
    return samples


@task
def parquet_task(
    parquet_path: str,
    model_name: str = "longevity_llm",
    fmt_filter: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    max_tokens: int = 500,
    temperature: float = 0.0,
    seed: int = 42,
) -> Task:
    """Generic eval task — runs any parquet benchmark file.

    Args:
        parquet_path: Absolute or relative path to the parquet file.
        model_name: Key in config/models.yaml.
        fmt_filter: Restrict to one format column value (e.g. 'mcq', 'binary', 'pairwise').
        limit: Max samples. None = all.
        dry_run: Skip model calls.
        max_tokens: Max output tokens per call.
        temperature: Sampling temperature.
        seed: Reproducibility seed.
    """
    model_cfg = _load_model_cfg(model_name)
    path = Path(parquet_path)

    if not path.exists():
        raise FileNotFoundError(f"Parquet not found: {path}")

    samples = load_parquet_samples(path, limit, fmt_filter)

    baseline_type = model_cfg.get("type") == "baseline"
    strategy = model_cfg.get("strategy", "")

    if baseline_type and strategy == "random":
        slvr = random_baseline_solver(seed=seed)
    elif baseline_type and strategy == "majority":
        slvr = majority_baseline_solver(
            fmt_majority=_compute_fmt_majority(path, samples),
        )
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

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
    population_prior_baseline_solver,
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

# Stricter instructions appended to the user turn for thinking models.
# These fire after the <think> block so the model sees the constraint
# immediately before it produces its visible answer.
_THINKING_USER_SUFFIX: dict[str, str] = {
    "mcq":        "\n\nIMPORTANT: Your final answer must be exactly one letter — A, B, C, or D. Nothing else.",
    "binary":     "\n\nIMPORTANT: Your final answer must be exactly one letter — A or B. Nothing else.",
    "pairwise":   "\n\nIMPORTANT: Your final answer must be exactly one letter — A or B. Nothing else.",
    "ternary":    "\n\nIMPORTANT: Your final answer must be exactly one label word. Nothing else.",
    "regression": "\n\nIMPORTANT: Your final answer must be exactly one integer. No units, no words, nothing else.",
}


def _row_to_sample(row: dict[str, Any], index: int, is_thinking: bool = False) -> Sample:
    messages = _ensure_messages(row["messages"])
    fmt = str(row.get("format") or "").lower()
    sys_instruction = _FORMAT_INSTRUCTIONS.get(fmt, "")
    user_suffix = _THINKING_USER_SUFFIX.get(fmt, "") if is_thinking else ""

    # messages layout: [system, user, assistant(gold)]
    # Build input as everything except the final assistant turn.
    processed: list[dict[str, str]] = []
    body = messages[:-1]
    for i, m in enumerate(body):
        role = m.get("role")
        content = m["content"]
        if i == 0 and role == "system" and sys_instruction:
            content = content + sys_instruction
        # Append format reminder to the last user message for thinking models.
        if user_suffix and i == len(body) - 1 and role == "user":
            content = content + user_suffix
        processed.append({"role": role, "content": content})

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


def _get_target(msgs_val: Any) -> str:
    msgs = _ensure_messages(msgs_val)
    return str(msgs[-1]["content"]).strip()


def _compute_fmt_majority(test_path: Path, test_samples: list[Sample]) -> dict[str, str]:
    """Compute per-format majority/mean label from the training split (if available).

    Classification formats (mcq, binary, pairwise): most-frequent label.
    Regression format: mean of training targets rounded to nearest integer.
    Falls back to test samples when no train file found.
    """
    train_path = Path(str(test_path).replace("_test.parquet", "_train.parquet"))
    if not train_path.exists():
        # Also try task_b path (no processed/ subdir)
        alt = test_path.parent / test_path.name.replace("_test.parquet", "_train.parquet")
        train_path = alt if alt.exists() else None

    fmt_majority: dict[str, str] = {}
    train_df: pd.DataFrame | None = None
    if train_path:
        train_df = pd.read_parquet(train_path)

    for fmt in ("mcq", "binary", "pairwise"):
        if train_df is not None and "format" in train_df.columns:
            rows = train_df[train_df["format"] == fmt]
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

    # Regression: majority baseline = mean of training targets (MAE minimizer is median,
    # but mean is a reasonable constant predictor and avoids needing sorted data).
    if train_df is not None and "format" in train_df.columns:
        reg_rows = train_df[train_df["format"] == "regression"]
    else:
        reg_rows = pd.DataFrame()

    if not reg_rows.empty:
        reg_targets = reg_rows["messages"].apply(_get_target).tolist()
    else:
        reg_targets = [s.target for s in test_samples
                       if (s.metadata or {}).get("format") == "regression"]

    if reg_targets:
        vals = []
        for t in reg_targets:
            try:
                vals.append(float(t.strip()))
            except ValueError:
                pass
        if vals:
            fmt_majority["regression"] = str(round(sum(vals) / len(vals)))

    fmt_majority.setdefault("default", "A")
    logger.info("majority baseline labels: %s", fmt_majority)
    return fmt_majority


def _compute_regression_range(test_path: Path, test_samples: list[Sample]) -> tuple[int, int]:
    """Return (min, max) of regression targets from training data for random baseline."""
    train_path = Path(str(test_path).replace("_test.parquet", "_train.parquet"))
    if not train_path.exists():
        alt = test_path.parent / test_path.name.replace("_test.parquet", "_train.parquet")
        train_path = alt if alt.exists() else None

    targets: list[float] = []
    if train_path:
        df = pd.read_parquet(train_path)
        if "format" in df.columns:
            rows = df[df["format"] == "regression"]
            for t in rows["messages"].apply(_get_target):
                try:
                    targets.append(float(t.strip()))
                except ValueError:
                    pass

    if not targets:
        targets = []
        for s in test_samples:
            if (s.metadata or {}).get("format") == "regression":
                try:
                    targets.append(float(s.target.strip()))
                except ValueError:
                    pass

    if not targets:
        return (20, 90)  # fallback: age range
    return (int(min(targets)), int(max(targets)))


def load_parquet_samples(
    parquet_path: Path,
    limit: int | None = None,
    fmt_filter: str | None = None,
    is_thinking: bool = False,
    bootstrap_seed: int | None = None,
) -> list[Sample]:
    df = pd.read_parquet(parquet_path)
    if fmt_filter:
        df = df[df["format"] == fmt_filter]
    # Bootstrap: shuffle rows with a reproducible seed before applying limit.
    # Different bootstrap_seed values → different subsets → variance for whisker plots.
    if bootstrap_seed is not None:
        df = df.sample(frac=1, random_state=bootstrap_seed).reset_index(drop=True)
    if limit is not None:
        df = df.head(limit)
    samples = [_row_to_sample(row.to_dict(), i, is_thinking=is_thinking)
               for i, (_, row) in enumerate(df.iterrows())]
    logger.info(
        "loaded %d samples from %s (fmt=%s limit=%s thinking=%s bootstrap_seed=%s)",
        len(samples), parquet_path.name, fmt_filter, limit, is_thinking, bootstrap_seed,
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
    bootstrap_seed: int | None = None,
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

    is_thinking: bool = bool(
        (model_cfg.get("extra_body") or {})
        .get("chat_template_kwargs", {})
        .get("enable_thinking", False)
    )
    # Model config max_tokens takes precedence over CLI default when thinking is on.
    if "max_tokens" in model_cfg:
        max_tokens = model_cfg["max_tokens"]
    samples = load_parquet_samples(path, limit, fmt_filter,
                                   is_thinking=is_thinking, bootstrap_seed=bootstrap_seed)

    baseline_type = model_cfg.get("type") == "baseline"
    strategy = model_cfg.get("strategy", "")

    if baseline_type and strategy == "random":
        slvr = random_baseline_solver(
            seed=seed,
            regression_range=_compute_regression_range(path, samples),
        )
    elif baseline_type and strategy == "majority":
        slvr = majority_baseline_solver(
            fmt_majority=_compute_fmt_majority(path, samples),
        )
    elif baseline_type and strategy == "population_prior":
        repo_root = _MODELS_YAML.parent.parent
        csv_rel = model_cfg["csv_path"]
        csv_abs = csv_rel if Path(csv_rel).is_absolute() else str(repo_root / csv_rel)
        slvr = population_prior_baseline_solver(
            csv_path=csv_abs,
            year_col=model_cfg.get("year_col", "POPESTIMATE2025"),
            age_min=int(model_cfg.get("age_min", 20)),
            age_max=int(model_cfg.get("age_max", 90)),
            seed=seed,
        )
    else:
        slvr = litellm_solver(
            model_cfg=model_cfg,
            model_name=model_name,
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

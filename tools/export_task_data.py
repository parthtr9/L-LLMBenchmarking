"""Export task parquets → public/task_a_data.json and task_b_data.json.

These feed the Senescence and Lipidomics prompt-browser pages in the dashboard.
Each row contains: lb_id, format, pool, display_group, domain, metric, split,
question (truncated 1000 chars), gold answer, follow_up (truncated 400 chars).

Usage:
    .venv/bin/python -m tools.export_task_data
    .venv/bin/python -m tools.export_task_data --public-dir <path>
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent
_PUBLIC = _ROOT / "LongevityBench Design System" / "ui_kits" / "longevity_bench" / "public"

_TASKS: dict[str, dict[str, str]] = {
    "task_a": {
        "train": "data/task_a_senescence/processed/task_a_senescence_train.parquet",
        "test":  "data/task_a_senescence/processed/task_a_senescence_test.parquet",
    },
    "task_b": {
        "train": "data/task_b_lipidomics/task_b_lipidomics_train.parquet",
        "test":  "data/task_b_lipidomics/task_b_lipidomics_test.parquet",
    },
}


def _extract_row(row: dict[str, Any], split: str) -> dict[str, Any]:
    msgs = row["messages"]
    if isinstance(msgs, str):
        msgs = json.loads(msgs)
    user_msg = next((m["content"] for m in msgs if m["role"] == "user"), "")
    gold = next((m["content"] for m in msgs if m["role"] == "assistant"), "")
    meta = row.get("metadata") or "{}"
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    follow_up = ""
    if isinstance(meta, dict):
        follow_up = (meta.get("follow_up") or "")[:400]
    return {
        "lb_id": row["lb_id"],
        "format": row["format"],
        "pool": row.get("pool", ""),
        "display_group": row.get("display_group", ""),
        "domain": row.get("domain", ""),
        "metric": row.get("metric", ""),
        "split": split,
        "question": user_msg[:1000],
        "gold": gold,
        "follow_up": follow_up,
    }


def export_all(public_dir: Path) -> None:
    public_dir.mkdir(parents=True, exist_ok=True)
    for task_key, splits in _TASKS.items():
        rows: list[dict] = []
        for split, rel_path in splits.items():
            path = _ROOT / rel_path
            if not path.exists():
                logger.warning("not found, skipping: %s", path)
                continue
            df = pd.read_parquet(path)
            rows.extend(_extract_row(r.to_dict(), split) for _, r in df.iterrows())
            logger.info("%s %s: %d rows", task_key, split, len(df))

        out = public_dir / f"{task_key}_data.json"
        out.write_text(json.dumps({"task": task_key, "rows": rows}, indent=2), encoding="utf-8")
        logger.info("written → %s  (%d total rows)", out, len(rows))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-dir", type=Path, default=_PUBLIC)
    args = parser.parse_args()
    export_all(args.public_dir)
    print("\n=== Task data export complete ===")
    for task_key in _TASKS:
        out = args.public_dir / f"{task_key}_data.json"
        if out.exists():
            data = json.loads(out.read_text())
            print(f"  {task_key}_data.json: {len(data['rows'])} rows")


if __name__ == "__main__":
    main()

"""Build a 5-row smoke-test parquet for L-LLM thinking-mode eval.

Picks 1 row of each format from Task A train (mcq, binary, pairwise) and
1 mcq + 1 regression from Task B train. Covers 5 distinct formats across
both tasks so the smoke run exercises the full scoring matrix.
"""
from __future__ import annotations

import pandas as pd

A_PATH = "data/task_a_senescence/processed/task_a_senescence_train.parquet"
B_PATH = "data/task_b_lipidomics/task_b_lipidomics_train.parquet"
OUT = "data/smoke_thinking_5.parquet"


def _pick(df: pd.DataFrame, fmt: str, seed: int) -> pd.DataFrame:
    return df[df["format"] == fmt].sample(n=1, random_state=seed)


def main() -> None:
    a = pd.read_parquet(A_PATH)
    b = pd.read_parquet(B_PATH)
    rows = pd.concat(
        [
            _pick(a, "mcq", 42),
            _pick(a, "binary", 42),
            _pick(a, "pairwise", 42),
            _pick(b, "mcq", 42),
            _pick(b, "regression", 42),
        ],
        ignore_index=True,
    )
    rows.to_parquet(OUT, index=False)
    print(f"wrote {OUT}  rows={len(rows)}")
    print(rows[["lb_id", "format", "pool"]].to_string(index=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Compare model performance on two dataset versions.

Runs both files through Inspect AI in isolated output dirs under
outputs/compare/ — never touches data/ or the main outputs/inspect/ logs.
No prediction cache used.

Usage:
    .venv/bin/python tools/compare_datasets.py \
        --a data/task_a_senescence/processed/task_a_senescence_old_train.parquet \
        --b data/task_a_senescence/processed/task_a_senescence_train.json \
        --models longevity_llm,claude_sonnet,random_baseline,majority_baseline,population_prior_baseline
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from collections import defaultdict

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable
COMPARE_DIR = ROOT / "outputs" / "compare"


# ── loaders ──────────────────────────────────────────────────────────────────

def load_file(path: Path) -> pd.DataFrame:
    """Load parquet or JSON array into DataFrame."""
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if path.suffix in (".json", ".jsonl"):
        raw = path.read_text()
        data = json.loads(raw)
        if isinstance(data, list):
            return pd.DataFrame(data)
        if isinstance(data, dict) and "rows" in data:
            return pd.DataFrame(data["rows"])
        raise ValueError(f"Unrecognised JSON structure in {path}")
    raise ValueError(f"Unsupported file type: {path.suffix}")


def to_parquet(df: pd.DataFrame, dest: Path) -> Path:
    """Write DataFrame to a parquet file, return path."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dest, index=False)
    return dest


# ── eval runner ───────────────────────────────────────────────────────────────

def run_eval(parquet: Path, models: list[str], log_dir: Path) -> int:
    cmd = [
        PYTHON, "-m", "src.eval.run_inspect",
        "--parquet", str(parquet),
        "--models", ",".join(models),
        "--log-dir", str(log_dir),
    ]
    print(f"\n  running: {' '.join(cmd)}\n")
    return subprocess.run(cmd, cwd=ROOT).returncode


# ── result parser ─────────────────────────────────────────────────────────────

def parse_eval_dir(log_dir: Path) -> dict[str, dict[str, dict]]:
    """Parse all .eval logs under log_dir.

    Returns {model_id: {lb_id: {score, pass, answer, gold, format, metric}}}
    """
    try:
        from inspect_ai.log import read_eval_log
    except ImportError:
        print("  ERROR: inspect_ai not installed")
        sys.exit(1)

    results: dict[str, dict[str, dict]] = {}

    for model_dir in sorted(log_dir.iterdir()):
        if not model_dir.is_dir():
            continue
        model_id = model_dir.name
        results[model_id] = {}

        for eval_file in sorted(model_dir.glob("*.eval")):
            try:
                log = read_eval_log(str(eval_file))
            except Exception as e:
                print(f"  WARN: could not read {eval_file.name}: {e}")
                continue

            for sample in (log.samples or []):
                lb_id = str(sample.id)
                score_obj = (sample.scores or {})
                # try longebench_scorer first, fall back to first scorer
                score_val = None
                pass_val = None
                for k, v in score_obj.items():
                    score_val = float(v.value) if v.value is not None else None
                    pass_val = bool(v.value) if v.value is not None else None
                    break

                meta = sample.metadata or {}
                results[model_id][lb_id] = {
                    "score": score_val,
                    "pass": pass_val,
                    "answer": (sample.output.completion if sample.output else None),
                    "gold": meta.get("gold"),
                    "format": meta.get("format") or meta.get("metric", "?"),
                    "metric": meta.get("metric", "?"),
                }

    return results


# ── comparison ────────────────────────────────────────────────────────────────

def compare(
    res_a: dict[str, dict[str, dict]],
    res_b: dict[str, dict[str, dict]],
    label_a: str,
    label_b: str,
) -> None:
    all_models = sorted(set(res_a) | set(res_b))

    print("\n" + "═" * 72)
    print(f"  DATASET COMPARISON")
    print(f"  A = {label_a}")
    print(f"  B = {label_b}")
    print("═" * 72)

    for model in all_models:
        a_data = res_a.get(model, {})
        b_data = res_b.get(model, {})

        all_ids = sorted(set(a_data) | set(b_data))
        if not all_ids:
            continue

        # ── per-format breakdown ─────────────────────────────────────────────
        fmt_a: dict[str, list[float]] = defaultdict(list)
        fmt_b: dict[str, list[float]] = defaultdict(list)

        for lb_id in all_ids:
            ar = a_data.get(lb_id)
            br = b_data.get(lb_id)
            fmt = (ar or br or {}).get("format", "?")
            if ar and ar["score"] is not None:
                fmt_a[fmt].append(ar["score"])
            if br and br["score"] is not None:
                fmt_b[fmt].append(br["score"])

        all_fmts = sorted(set(fmt_a) | set(fmt_b))

        a_overall = [s for v in fmt_a.values() for s in v]
        b_overall = [s for v in fmt_b.values() for s in v]
        a_avg = sum(a_overall) / len(a_overall) if a_overall else None
        b_avg = sum(b_overall) / len(b_overall) if b_overall else None

        print(f"\n  {'─'*68}")
        print(f"  Model: {model}")
        print(f"  {'─'*68}")
        header = f"  {'Format':<16}  {'A score':>9}  {'B score':>9}  {'Δ (B−A)':>9}  {'A n':>5}  {'B n':>5}"
        print(header)
        print(f"  {'─'*68}")

        for fmt in all_fmts:
            av = fmt_a.get(fmt, [])
            bv = fmt_b.get(fmt, [])
            a_s = sum(av) / len(av) if av else None
            b_s = sum(bv) / len(bv) if bv else None
            delta = (b_s - a_s) if (a_s is not None and b_s is not None) else None
            a_str = f"{a_s:.4f}" if a_s is not None else "  —"
            b_str = f"{b_s:.4f}" if b_s is not None else "  —"
            d_str = (f"{delta:+.4f}" if delta is not None else "  —")
            flag = "▲" if (delta and delta > 0.01) else ("▼" if (delta and delta < -0.01) else " ")
            print(f"  {fmt:<16}  {a_str:>9}  {b_str:>9}  {flag}{d_str:>8}  {len(av):>5}  {len(bv):>5}")

        print(f"  {'─'*68}")
        a_avg_str = f"{a_avg:.4f}" if a_avg is not None else "  —"
        b_avg_str = f"{b_avg:.4f}" if b_avg is not None else "  —"
        delta_avg = (b_avg - a_avg) if (a_avg is not None and b_avg is not None) else None
        d_avg_str = (f"{delta_avg:+.4f}" if delta_avg is not None else "  —")
        flag = "▲" if (delta_avg and delta_avg > 0.01) else ("▼" if (delta_avg and delta_avg < -0.01) else " ")
        print(f"  {'OVERALL':<16}  {a_avg_str:>9}  {b_avg_str:>9}  {flag}{d_avg_str:>8}  {len(a_overall):>5}  {len(b_overall):>5}")

    # ── prompt diff ──────────────────────────────────────────────────────────
    # Use first model that has data in both
    ref_model = next((m for m in all_models if res_a.get(m) and res_b.get(m)), None)
    if ref_model:
        ids_a = set(res_a[ref_model])
        ids_b = set(res_b[ref_model])
        only_a = ids_a - ids_b
        only_b = ids_b - ids_a
        shared = ids_a & ids_b
        print(f"\n  {'─'*68}")
        print(f"  Prompt overlap ({ref_model})")
        print(f"  {'─'*68}")
        print(f"  Shared lb_ids : {len(shared)}")
        print(f"  Only in A     : {len(only_a)}")
        print(f"  Only in B     : {len(only_b)}")
        if only_a:
            print(f"  Sample only-A : {sorted(only_a)[:5]}")
        if only_b:
            print(f"  Sample only-B : {sorted(only_b)[:5]}")

    print("\n" + "═" * 72)


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Compare model results on two dataset versions.")
    parser.add_argument("--a", required=True, type=Path, help="First dataset (parquet or JSON)")
    parser.add_argument("--b", required=True, type=Path, help="Second dataset (parquet or JSON)")
    parser.add_argument("--models", required=True, help="Comma-separated model IDs")
    parser.add_argument("--skip-eval", action="store_true", help="Skip running eval (use existing logs in outputs/compare/)")
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",")]
    path_a: Path = args.a.resolve()
    path_b: Path = args.b.resolve()

    for p in [path_a, path_b]:
        if not p.exists():
            print(f"ERROR: file not found: {p}")
            sys.exit(1)

    log_dir_a = COMPARE_DIR / "version_a"
    log_dir_b = COMPARE_DIR / "version_b"
    log_dir_a.mkdir(parents=True, exist_ok=True)
    log_dir_b.mkdir(parents=True, exist_ok=True)

    # Convert non-parquet inputs to temp parquet inside outputs/compare/
    def ensure_parquet(path: Path, tag: str) -> Path:
        if path.suffix == ".parquet":
            return path
        print(f"\n  Converting {path.name} → parquet...")
        df = load_file(path)
        out = COMPARE_DIR / f"_tmp_{tag}.parquet"
        return to_parquet(df, out)

    if not args.skip_eval:
        pq_a = ensure_parquet(path_a, "a")
        pq_b = ensure_parquet(path_b, "b")

        print(f"\n  ── Evaluating A: {path_a.name} ──")
        rc = run_eval(pq_a, models, log_dir_a)
        if rc != 0:
            print(f"\n  WARN: eval A exited {rc}")

        print(f"\n  ── Evaluating B: {path_b.name} ──")
        rc = run_eval(pq_b, models, log_dir_b)
        if rc != 0:
            print(f"\n  WARN: eval B exited {rc}")
    else:
        print("\n  --skip-eval set — using existing logs in outputs/compare/")

    print("\n  Parsing results...")
    res_a = parse_eval_dir(log_dir_a)
    res_b = parse_eval_dir(log_dir_b)

    compare(res_a, res_b, label_a=path_a.name, label_b=path_b.name)

    # Save JSON diff to outputs/compare/
    diff_path = COMPARE_DIR / "diff.json"
    diff_path.write_text(json.dumps({
        "a": path_a.name, "b": path_b.name, "models": models,
        "results_a": {m: {k: v for k, v in d.items()} for m, d in res_a.items()},
        "results_b": {m: {k: v for k, v in d.items()} for m, d in res_b.items()},
    }, indent=2, default=str))
    print(f"\n  Full diff saved to: outputs/compare/diff.json\n")


if __name__ == "__main__":
    main()

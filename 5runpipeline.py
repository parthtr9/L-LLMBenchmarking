#!/usr/bin/env python3
"""
5-run bootstrap pipeline for whisker plots.

Runs all discovered train datasets 5 times with different bootstrap seeds
(different 40-sample subsets each time), then exports to data.json.

Usage:
    .venv/bin/python 5runpipeline.py

Each run uses a different random 40-row subset of the train parquet.
After 5 runs the export produces 5 score entries per model in data.json,
which the Compare view uses for box/whisker plots.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT       = Path(__file__).resolve().parent
MODELS_YAML = ROOT / "config" / "models.yaml"
DATA_ROOT  = ROOT / "data"
LOG_DIR    = ROOT / "outputs" / "inspect"
DATA_JSON  = ROOT / "LongevityBench Design System" / "ui_kits" / "longevity_bench" / "public" / "data.json"
PYTHON     = sys.executable

N_RUNS     = 5
LIMIT      = 40   # samples per run per dataset


# ── helpers ───────────────────────────────────────────────────────────────────

def header(text: str) -> None:
    print(f"\n{'─' * 60}\n  {text}\n{'─' * 60}")


def run_cmd(cmd: list[str]) -> int:
    print(f"\n  $ {' '.join(cmd)}\n")
    return subprocess.run(cmd).returncode


def confirm(prompt: str) -> bool:
    while True:
        ans = input(f"\n  {prompt} [y/n]: ").strip().lower()
        if ans in ("y", "yes"): return True
        if ans in ("n", "no"):  return False
        print("  enter y or n")


# ── dataset discovery ─────────────────────────────────────────────────────────

def discover_train_sets() -> list[dict]:
    """Return all *_train.parquet files found under data/*/processed/ or data/*/."""
    found = []
    for task_dir in sorted(p for p in DATA_ROOT.iterdir() if p.is_dir() and not p.name.startswith(".")):
        for search_dir in [task_dir / "processed", task_dir]:
            if not search_dir.is_dir():
                continue
            trains = sorted(
                p for p in search_dir.glob("*_train.parquet")
                if not p.stem.endswith(("_30", "_100"))
            )
            if trains:
                path = trains[0]
                try:
                    df = pd.read_parquet(path)
                    n = len(df)
                    formats = sorted(df["format"].dropna().unique().tolist()) if "format" in df.columns else []
                except Exception:
                    n, formats = 0, []
                found.append({"label": task_dir.name, "path": path, "n": n, "formats": formats})
                break
    return found


# ── model selection ───────────────────────────────────────────────────────────

def choose_models(registry: dict) -> list[str]:
    header("Choose models")
    available = list(registry.keys())
    print("\n  Available models:")
    for i, name in enumerate(available, 1):
        cfg = registry[name]
        kind = cfg.get("type", "llm")
        model_str = cfg.get("litellm_model", f"baseline:{cfg.get('strategy','')}")
        tag = " [baseline]" if kind == "baseline" else ""
        print(f"    {i:2d}) {name:<30s} ({model_str}){tag}")

    print("\n  Enter numbers (e.g. 1,3,4,5) or press Enter for all non-thinking models")
    default = [m for m in available if m != "longevity_llm_thinking"]

    while True:
        raw = input("  models: ").strip()
        if not raw:
            print(f"\n  Using: {', '.join(default)}")
            return default
        parts = [p.strip() for p in raw.split(",")]
        resolved, bad = [], False
        for p in parts:
            if p.isdigit() and 1 <= int(p) <= len(available):
                resolved.append(available[int(p) - 1])
            elif p in available:
                resolved.append(p)
            else:
                print(f"  unknown: {p!r}")
                bad = True
                break
        if not bad and resolved:
            print(f"\n  Using: {', '.join(resolved)}")
            return resolved


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n  LongevityBench · 5-run bootstrap pipeline")
    print(f"  {N_RUNS} runs × {LIMIT} samples × all train datasets → whisker plots\n")

    with open(MODELS_YAML) as f:
        registry = yaml.safe_load(f)["models"]

    train_sets = discover_train_sets()
    if not train_sets:
        print("  No *_train.parquet files found under data/*/")
        sys.exit(1)

    print("  Train datasets found:")
    for ds in train_sets:
        fmts = ", ".join(ds["formats"]) if ds["formats"] else "?"
        print(f"    {ds['label']:<30s}  n={ds['n']}  formats: {fmts}")

    models = choose_models(registry)

    # Cost estimate
    llm_models = [m for m in models if registry[m].get("type") != "baseline"]
    total_calls = N_RUNS * len(train_sets) * LIMIT * len(llm_models)
    print(f"\n  Plan:")
    print(f"    {N_RUNS} bootstrap runs × {len(train_sets)} dataset(s) × {LIMIT} samples × {len(llm_models)} LLM model(s)")
    print(f"    = ~{total_calls} LLM API calls total")
    print(f"    Baselines (×{len(models) - len(llm_models)}) are free")
    print(f"    Logs → outputs/inspect/<model>/ (5 .eval files per model per task)")

    if not confirm("Start all 5 runs now?"):
        print("  Aborted.")
        sys.exit(0)

    model_str = ",".join(models)
    any_ok = False

    for run_i in range(1, N_RUNS + 1):
        header(f"Run {run_i} / {N_RUNS}  (bootstrap_seed={run_i})")
        for ds in train_sets:
            print(f"\n  dataset: {ds['label']}  ({ds['path'].name})")
            cmd = [
                PYTHON, "-m", "src.eval.run_inspect",
                "--parquet", str(ds["path"]),
                "--models", model_str,
                "--limit", str(LIMIT),
                "--bootstrap-seed", str(run_i),
                "--seed", str(run_i),
            ]
            rc = run_cmd(cmd)
            if rc != 0:
                print(f"\n  run {run_i} / {ds['label']} exited with code {rc}")
                if not confirm("Continue to next?"):
                    print("  Stopping.")
                    sys.exit(rc)
            else:
                any_ok = True

    if not any_ok:
        print("\n  No runs completed. Nothing to export.")
        sys.exit(1)

    # Export
    header("Export → data.json")
    rc = run_cmd([
        PYTHON, "-m", "tools.export_inspect_logs",
        "--log-dir", str(LOG_DIR),
        "--out", str(DATA_JSON),
    ])
    if rc != 0:
        print(f"  Export failed (exit code {rc}).")
        sys.exit(rc)

    print(f"\n  Done. Dashboard JSON updated: {DATA_JSON.relative_to(ROOT)}")
    print("  Open http://localhost:8765/ → Compare models to see whisker plots.")
    print("  (Run: cd 'LongevityBench Design System/ui_kits/longevity_bench' && python3 -m http.server 8765)\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
LongevityBench pipeline — dynamic dataset eval → export → dashboard.
Drop any parquet benchmark file under data/<task>/processed/ and it appears here.
Run from repo root:

    .venv/bin/python pipeline.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent
MODELS_YAML = ROOT / "config" / "models.yaml"
DATA_ROOT = ROOT / "data"
LOG_DIR = ROOT / "outputs" / "inspect"
DATA_JSON = ROOT / "LongevityBench Design System" / "ui_kits" / "longevity_bench" / "public" / "data.json"
DASHBOARD_DIR = ROOT / "LongevityBench Design System" / "ui_kits" / "longevity_bench"
PYTHON = sys.executable


# ── helpers ──────────────────────────────────────────────────────────────────

def header(text: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {text}")
    print(f"{'─' * 60}")


def confirm(prompt: str) -> bool:
    while True:
        ans = input(f"\n  {prompt} [y/n]: ").strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("  enter y or n")


def run_cmd(cmd: list[str]) -> int:
    print(f"\n  running: {' '.join(cmd)}\n")
    return subprocess.run(cmd).returncode


# ── dataset discovery ─────────────────────────────────────────────────────────

def discover_datasets() -> list[dict]:
    """
    Scan data/<task>/processed/ for *_test.parquet and *_train.parquet.
    Returns list of {label, task_dir, test_path, train_path, formats, n_test, n_train}.
    """
    datasets = []
    for processed_dir in sorted(DATA_ROOT.glob("*/processed")):
        task_dir = processed_dir.parent
        task_name = task_dir.name

        test_files = sorted(processed_dir.glob("*_test.parquet"))
        train_files = sorted(processed_dir.glob("*_train.parquet"))

        if not test_files and not train_files:
            continue

        info: dict = {
            "label": task_name,
            "task_dir": task_dir,
            "test_path": test_files[0] if test_files else None,
            "train_path": train_files[0] if train_files else None,
            "formats": [],
            "n_test": 0,
            "n_train": 0,
        }

        if info["test_path"]:
            try:
                df = pd.read_parquet(info["test_path"])
                info["n_test"] = len(df)
                info["formats"] = sorted(df["format"].dropna().unique().tolist()) if "format" in df.columns else []
            except Exception:
                pass

        if info["train_path"]:
            try:
                df = pd.read_parquet(info["train_path"])
                info["n_train"] = len(df)
            except Exception:
                pass

        datasets.append(info)

    return datasets


# ── step 1: choose models ────────────────────────────────────────────────────

def step_choose_models(registry: dict) -> list[str]:
    header("STEP 1 — Choose models to evaluate")

    available = list(registry.keys())
    print("\n  Available models:")
    for i, name in enumerate(available, 1):
        cfg = registry[name]
        kind = cfg.get("type", "llm")
        model_str = cfg.get("litellm_model", f"baseline:{cfg.get('strategy','')}")
        print(f"    {i:2d}) {name:<28s}  ({model_str})" + (" [baseline]" if kind == "baseline" else ""))

    print("\n  Enter model numbers separated by commas (e.g. 1,5,6)")
    print("  or press Enter for default: longevity_llm,majority_baseline,random_baseline")

    while True:
        raw = input("  models: ").strip()
        if not raw:
            selected = ["longevity_llm", "majority_baseline", "random_baseline"]
            break
        parts = [p.strip() for p in raw.split(",")]
        resolved: list[str] = []
        bad = False
        for p in parts:
            if p.isdigit():
                idx = int(p) - 1
                if 0 <= idx < len(available):
                    resolved.append(available[idx])
                else:
                    print(f"  invalid number: {p}")
                    bad = True
                    break
            elif p in available:
                resolved.append(p)
            else:
                print(f"  unknown model: {p!r} — choose from {available}")
                bad = True
                break
        if not bad and resolved:
            selected = resolved
            break

    print(f"\n  Selected: {', '.join(selected)}")
    return selected


# ── step 2: choose dataset ───────────────────────────────────────────────────

def step_choose_dataset(datasets: list[dict]) -> tuple[Path, str | None, int | None]:
    """Returns (parquet_path, fmt_filter, limit)."""
    header("STEP 2 — Choose dataset")

    if not datasets:
        print("\n  No datasets found under data/*/processed/")
        print("  Add a parquet benchmark file there and re-run.")
        sys.exit(1)

    print("\n  Available datasets:")
    for i, ds in enumerate(datasets, 1):
        splits = []
        if ds["test_path"]:
            splits.append(f"test={ds['n_test']}")
        if ds["train_path"]:
            splits.append(f"train={ds['n_train']}")
        fmts = ", ".join(ds["formats"]) if ds["formats"] else "?"
        print(f"    {i}) {ds['label']:<30s}  [{', '.join(splits)}]  formats: {fmts}")

    while True:
        raw = input("\n  dataset number: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(datasets):
            ds = datasets[int(raw) - 1]
            break
        print(f"  enter 1–{len(datasets)}")

    # Choose split
    available_splits = []
    if ds["test_path"]:
        available_splits.append(("test", ds["test_path"], ds["n_test"]))
    if ds["train_path"]:
        available_splits.append(("train", ds["train_path"], ds["n_train"]))

    if len(available_splits) == 1:
        split_name, parquet_path, n_total = available_splits[0]
        print(f"\n  Split: {split_name} ({n_total} samples)")
    else:
        print("\n  Split:")
        for i, (name, _, n) in enumerate(available_splits, 1):
            print(f"    {i}) {name} ({n} samples)")
        while True:
            raw = input("  split: ").strip()
            if raw.isdigit() and 1 <= int(raw) <= len(available_splits):
                split_name, parquet_path, n_total = available_splits[int(raw) - 1]
                break
            print(f"  enter 1–{len(available_splits)}")

    # Choose format filter
    formats = ds["formats"]
    fmt_filter: str | None = None
    if formats:
        print(f"\n  Format filter (available: {', '.join(formats)}):")
        print(f"    0) all ({n_total} samples)")
        for i, f in enumerate(formats, 1):
            print(f"    {i}) {f}")
        raw = input("  format [0=all]: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(formats):
            fmt_filter = formats[int(raw) - 1]

    # Choose limit
    print(f"\n  Sample limit per model (default 20, none = all):")
    raw = input("  limit [20]: ").strip()
    if not raw:
        limit: int | None = 20
    elif raw.lower() == "none":
        limit = None
    else:
        try:
            limit = int(raw)
        except ValueError:
            print("  invalid — using 20")
            limit = 20

    print(f"\n  Dataset : {ds['label']} ({split_name})")
    print(f"  Parquet : {parquet_path.name}")
    print(f"  Format  : {fmt_filter or 'all'}")
    print(f"  Limit   : {limit or 'all'}")
    return parquet_path, fmt_filter, limit


# ── step 3: run eval ─────────────────────────────────────────────────────────

def step_run_eval(
    models: list[str],
    parquet_path: Path,
    fmt_filter: str | None,
    limit: int | None,
) -> bool:
    header("STEP 3 — Run evaluation")

    print(f"\n  Models  : {', '.join(models)}")
    print(f"  Parquet : {parquet_path.name}")
    print(f"  Format  : {fmt_filter or 'all'}")
    print(f"  Limit   : {limit or 'all'}")
    print(f"  Log dir : outputs/inspect/")

    if not confirm("Run eval now?"):
        print("  Skipping eval.")
        return False

    cmd = [
        PYTHON, "-m", "src.eval.run_inspect",
        "--parquet", str(parquet_path),
        "--models", ",".join(models),
    ]
    if fmt_filter:
        cmd += ["--fmt-filter", fmt_filter]
    if limit:
        cmd += ["--limit", str(limit)]

    print("\n  Starting eval...")
    rc = run_cmd(cmd)

    if rc != 0:
        print(f"\n  Eval exited with code {rc}. Some samples may have failed.")
        if not confirm("Continue to export anyway?"):
            print("  Stopping pipeline.")
            return False
    else:
        print("\n  Eval complete.")

    return True


# ── step 4: export logs ──────────────────────────────────────────────────────

def step_export() -> bool:
    header("STEP 4 — Export logs → dashboard JSON")

    print(f"\n  Source : outputs/inspect/")
    print(f"  Output : {DATA_JSON.relative_to(ROOT)}")

    if not confirm("Export now?"):
        print("  Skipping export.")
        return False

    cmd = [
        PYTHON, "-m", "tools.export_inspect_logs",
        "--log-dir", str(LOG_DIR),
        "--out", str(DATA_JSON),
    ]

    print("\n  Exporting...")
    rc = run_cmd(cmd)

    if rc != 0:
        print(f"\n  Export failed (exit code {rc}).")
        return False

    print("\n  Export complete.")
    return True


# ── step 5: serve dashboard ──────────────────────────────────────────────────

def step_serve() -> None:
    header("STEP 5 — Serve dashboard")

    print(f"\n  URL : http://localhost:8765/")

    if not confirm("Start HTTP server now? (blocks terminal until Ctrl-C)"):
        print("\n  To serve later:")
        print(f'    cd "{DASHBOARD_DIR}"')
        print("    python3 -m http.server 8765")
        return

    import os
    os.chdir(DASHBOARD_DIR)
    print("\n  Server on http://localhost:8765/ — Ctrl-C to stop\n")
    try:
        subprocess.run([PYTHON, "-m", "http.server", "8765"])
    except KeyboardInterrupt:
        print("\n  Server stopped.")


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n  LongevityBench Pipeline")
    print("  eval → export → dashboard\n")

    if not MODELS_YAML.exists():
        print(f"  ERROR: config/models.yaml not found")
        sys.exit(1)

    with open(MODELS_YAML) as f:
        registry = yaml.safe_load(f)["models"]

    datasets = discover_datasets()

    models = step_choose_models(registry)
    parquet_path, fmt_filter, limit = step_choose_dataset(datasets)
    eval_ok = step_run_eval(models, parquet_path, fmt_filter, limit)

    if eval_ok or LOG_DIR.exists():
        step_export()

    step_serve()

    header("Done")
    print("  Refresh http://localhost:8765/ to see results.\n")


if __name__ == "__main__":
    main()

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
GAP_REPORT = ROOT / "outputs" / "gap_analysis_report.md"
PRED_CACHE = ROOT / "outputs" / "prediction_cache.json"
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

def _find_parquets(task_dir: Path) -> tuple[Path | None, Path | None]:
    """Return (test_path, train_path) for a task dir.

    Checks processed/ subdir first; falls back to task dir itself.
    Skips *_test_30.parquet and other non-standard suffixes.
    """
    for search_dir in [task_dir / "processed", task_dir]:
        if not search_dir.is_dir():
            continue
        test_files = sorted(
            p for p in search_dir.glob("*_test.parquet")
            if not p.stem.endswith(("_30", "_100"))  # skip thinking-trace subsets
        )
        train_files = sorted(search_dir.glob("*_train.parquet"))
        if test_files or train_files:
            return (test_files[0] if test_files else None,
                    train_files[0] if train_files else None)
    return None, None


def discover_datasets() -> list[dict]:
    """Scan data/*/ for benchmark parquet pairs.

    Checks data/<task>/processed/ first, then data/<task>/ itself.
    Returns list of {label, task_dir, test_path, train_path, formats, n_test, n_train}.
    """
    datasets = []
    for task_dir in sorted(p for p in DATA_ROOT.iterdir() if p.is_dir() and not p.name.startswith(".")):
        test_path, train_path = _find_parquets(task_dir)
        if not test_path and not train_path:
            continue

        info: dict = {
            "label": task_dir.name,
            "task_dir": task_dir,
            "test_path": test_path,
            "train_path": train_path,
            "formats": [],
            "n_test": 0,
            "n_train": 0,
        }

        if test_path:
            try:
                df = pd.read_parquet(test_path)
                info["n_test"] = len(df)
                info["formats"] = sorted(df["format"].dropna().unique().tolist()) if "format" in df.columns else []
            except Exception:
                pass

        if train_path:
            try:
                df = pd.read_parquet(train_path)
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

def step_choose_dataset(datasets: list[dict]) -> list[tuple[Path, str | None, int | None]]:
    """Returns list of (parquet_path, fmt_filter, limit) — one entry per selected dataset."""
    header("STEP 2 — Choose dataset")

    if not datasets:
        print("\n  No datasets found under data/*/")
        print("  Add a parquet benchmark file there and re-run.")
        sys.exit(1)

    print("\n  Available datasets:")
    print(f"    0) ALL test sets  (runs every dataset — test split)")
    print(f"    t) ALL train sets (runs every dataset — train split)")
    for i, ds in enumerate(datasets, 1):
        splits = []
        if ds["test_path"]:
            splits.append(f"test={ds['n_test']}")
        if ds["train_path"]:
            splits.append(f"train={ds['n_train']}")
        fmts = ", ".join(ds["formats"]) if ds["formats"] else "?"
        print(f"    {i}) {ds['label']:<30s}  [{', '.join(splits)}]  formats: {fmts}")

    while True:
        raw = input(f"\n  dataset [0=all test, t=all train, 1–{len(datasets)}=single]: ").strip().lower()
        if raw == "0":
            selected_datasets = [ds for ds in datasets if ds["test_path"]]
            run_all_split = "test"
            break
        if raw == "t":
            selected_datasets = [ds for ds in datasets if ds["train_path"]]
            run_all_split = "train"
            break
        if raw.isdigit() and 1 <= int(raw) <= len(datasets):
            selected_datasets = [datasets[int(raw) - 1]]
            run_all_split = None
            break
        print(f"  enter 0, t, or 1–{len(datasets)}")

    # When running all test or all train
    if run_all_split:
        split_key = "test_path" if run_all_split == "test" else "train_path"
        n_key = "n_test" if run_all_split == "test" else "n_train"
        print(f"\n  Running all {len(selected_datasets)} {run_all_split} sets (no format filter)")
        raw = input("  sample limit per model per dataset [none=all]: ").strip()
        limit: int | None = None if (not raw or raw.lower() == "none") else int(raw)
        result = [(ds[split_key], None, limit) for ds in selected_datasets]
        for ds, (path, _, _) in zip(selected_datasets, result):
            print(f"    {ds['label']}: {path.name} ({ds[n_key]} samples)")
        return result

    # Single dataset
    ds = selected_datasets[0]

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
    print(f"\n  Sample limit per model (none = all {n_total} samples):")
    raw = input("  limit [none]: ").strip()
    if not raw or raw.lower() == "none":
        limit = None
    else:
        try:
            limit = int(raw)
        except ValueError:
            print("  invalid — using all")
            limit = None

    print(f"\n  Dataset : {ds['label']} ({split_name})")
    print(f"  Parquet : {parquet_path.name}")
    print(f"  Format  : {fmt_filter or 'all'}")
    print(f"  Limit   : {limit or 'all'}")
    return [(parquet_path, fmt_filter, limit)]


# ── step 3: run eval ─────────────────────────────────────────────────────────

def step_run_eval(
    models: list[str],
    dataset_runs: list[tuple[Path, str | None, int | None]],
) -> bool:
    header("STEP 3 — Run evaluation")

    total_samples = sum(
        (limit or 999999) for _, _, limit in dataset_runs
    )
    print(f"\n  Models   : {', '.join(models)}")
    print(f"  Datasets : {len(dataset_runs)}")
    for parquet_path, fmt_filter, limit in dataset_runs:
        print(f"    {parquet_path.name}  fmt={fmt_filter or 'all'}  limit={limit or 'all'}")
    print(f"  Log dir  : outputs/inspect/")

    if not confirm("Run eval now?"):
        print("  Skipping eval.")
        return False

    any_ok = False
    for parquet_path, fmt_filter, limit in dataset_runs:
        print(f"\n  ── {parquet_path.name} ──")
        cmd = [
            PYTHON, "-m", "src.eval.run_inspect",
            "--parquet", str(parquet_path),
            "--models", ",".join(models),
        ]
        if fmt_filter:
            cmd += ["--fmt-filter", fmt_filter]
        if limit:
            cmd += ["--limit", str(limit)]

        rc = run_cmd(cmd)
        if rc != 0:
            print(f"\n  Eval exited with code {rc}.")
            if not confirm("Continue to next dataset?"):
                print("  Stopping pipeline.")
                return any_ok
        else:
            print(f"\n  {parquet_path.name} complete.")
            any_ok = True

    return any_ok


# ── step 4: cache predictions ────────────────────────────────────────────────

def step_cache_predictions() -> None:
    header("STEP 4 — Cache LLM predictions")

    print(f"\n  Source : outputs/inspect/<model>/")
    print(f"  Output : {PRED_CACHE.relative_to(ROOT)}")
    print("  (Skips majority_baseline and random_baseline)")

    cmd = [
        PYTHON, "-m", "tools.cache_predictions",
        "--log-dir", str(LOG_DIR),
        "--out", str(PRED_CACHE),
    ]

    print("\n  Caching predictions...")
    rc = run_cmd(cmd)

    if rc != 0:
        print(f"\n  Cache step exited with code {rc} — continuing anyway.")
    else:
        print("\n  Prediction cache updated.")


# ── step 5: export logs ──────────────────────────────────────────────────────

def step_export() -> bool:
    header("STEP 5 — Export logs → dashboard JSON")

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


# ── step 5.5: export task prompt-browser data ────────────────────────────────

def step_export_task_data() -> None:
    header("STEP 5.5 — Export task prompt-browser data")

    print(f"\n  Output : public/task_a_data.json, public/task_b_data.json")

    cmd = [PYTHON, "-m", "tools.export_task_data"]
    print("\n  Exporting task data...")
    rc = run_cmd(cmd)

    if rc != 0:
        print(f"\n  Task data export failed (exit code {rc}) — continuing anyway.")
    else:
        print("\n  Task data export complete.")


# ── step 6: generate gap analysis report ─────────────────────────────────────

def _split_siblings(parquet_path: Path) -> tuple[Path | None, Path | None]:
    """Infer train/test parquet siblings for the selected benchmark file."""
    name = parquet_path.name
    train_path: Path | None = None
    test_path: Path | None = None

    if name.endswith("_test.parquet"):
        test_path = parquet_path
        train_path = parquet_path.with_name(name.replace("_test.parquet", "_train.parquet"))
    elif name.endswith("_train.parquet"):
        train_path = parquet_path
        test_path = parquet_path.with_name(name.replace("_train.parquet", "_test.parquet"))
    else:
        test_path = parquet_path

    if train_path is not None and not train_path.exists():
        train_path = None
    if test_path is not None and not test_path.exists():
        test_path = None
    return train_path, test_path


def step_gap_report(dataset_runs: list[tuple[Path, str | None, int | None]]) -> bool:
    header("STEP 6 — Generate gap analysis report")

    # Collect all train/test siblings across all selected datasets
    all_train: list[Path] = []
    all_test: list[Path] = []
    for parquet_path, _, _ in dataset_runs:
        train_path, test_path = _split_siblings(parquet_path)
        if train_path:
            all_train.append(train_path)
        if test_path:
            all_test.append(test_path)

    print(f"\n  Data JSON : {DATA_JSON.relative_to(ROOT)}")
    for p in all_train:
        print(f"  Train     : {p.relative_to(ROOT)}")
    for p in all_test:
        print(f"  Test      : {p.relative_to(ROOT)}")
    print(f"  Output    : {GAP_REPORT.relative_to(ROOT)}")

    if not DATA_JSON.exists():
        print("\n  Dashboard JSON not found. Run export first.")
        return False

    if not confirm("Generate gap analysis report now?"):
        print("  Skipping gap analysis report.")
        return False

    cmd = [
        PYTHON, "-m", "src.analysis.gap_analysis",
        "--data", str(DATA_JSON),
        "--out", str(GAP_REPORT),
    ]
    for p in all_train:
        cmd += ["--train", str(p)]
    for p in all_test:
        cmd += ["--test", str(p)]

    print("\n  Generating report...")
    rc = run_cmd(cmd)

    if rc != 0:
        print(f"\n  Gap analysis failed (exit code {rc}).")
        return False

    print("\n  Gap analysis report complete.")
    return True


# ── step 6.5: trace scoring ──────────────────────────────────────────────────

def step_trace_scoring() -> None:
    header("STEP 6.5 — Score L-LLM thinking traces (V5 + Claude oracle)")

    if not DATA_JSON.exists():
        print("\n  data.json not found — skipping trace scoring.")
        return

    if not confirm("Run V5 trace scorer (gene verification + keyword consistency)?"):
        print("  Skipping trace scoring.")
        return

    rc = run_cmd([PYTHON, "-m", "src.trace_scorer.trace_scorer"])
    if rc != 0:
        print(f"\n  V5 scorer exited with code {rc}.")
        return

    print("\n  V5 scoring complete.")

    if not confirm("Run Claude oracle tier (~$0.01/trace, uses ANTHROPIC_API_KEY)?"):
        print("  Skipping oracle.")
        return

    rc = run_cmd([PYTHON, "-m", "src.trace_scorer.run_oracle"])
    if rc != 0:
        print(f"\n  Oracle exited with code {rc}.")
        return

    print("\n  Oracle scoring complete.")


# ── step 7: serve dashboard ──────────────────────────────────────────────────

def step_serve() -> None:
    header("STEP 7 — Serve dashboard")

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
    print("  eval → export → report → dashboard\n")

    if not MODELS_YAML.exists():
        print(f"  ERROR: config/models.yaml not found")
        sys.exit(1)

    with open(MODELS_YAML) as f:
        registry = yaml.safe_load(f)["models"]

    datasets = discover_datasets()

    models = step_choose_models(registry)
    dataset_runs = step_choose_dataset(datasets)
    eval_ok = step_run_eval(models, dataset_runs)

    if eval_ok or LOG_DIR.exists():
        step_cache_predictions()

    exported = False
    if eval_ok or LOG_DIR.exists():
        exported = step_export()

    if exported or DATA_JSON.exists():
        step_export_task_data()

    if exported or DATA_JSON.exists():
        step_gap_report(dataset_runs)

    if exported or DATA_JSON.exists():
        step_trace_scoring()

    step_serve()

    header("Done")
    print("  Refresh http://localhost:8765/ to see results.\n")


if __name__ == "__main__":
    main()

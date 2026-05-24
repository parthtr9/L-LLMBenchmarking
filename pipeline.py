#!/usr/bin/env python3
"""
LongevityBench pipeline — run evals, export logs, refresh dashboard.
Prompts y/n at each step. Run from repo root:

    .venv/bin/python pipeline.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent
MODELS_YAML = ROOT / "config" / "models.yaml"
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


def choose(prompt: str, options: list[str]) -> str:
    print(f"\n  {prompt}")
    for i, opt in enumerate(options, 1):
        print(f"    {i}) {opt}")
    while True:
        raw = input("  enter number or value: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        if raw in options:
            return raw
        print(f"  invalid — enter 1–{len(options)} or the value directly")


def run_cmd(cmd: list[str]) -> int:
    print(f"\n  running: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    return result.returncode


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


# ── step 2: choose task ──────────────────────────────────────────────────────

def step_choose_task() -> tuple[str, int]:
    header("STEP 2 — Choose task and sample limit")

    lb_id = choose(
        "LongeBench task ID:",
        ["LB-0038", "LB-0042", "LB-0051", "LB-0067", "LB-0072", "LB-0090"],
    )

    print(f"\n  Sample limit (default 50, full eval = None):")
    raw = input("  limit [50]: ").strip()
    if not raw:
        limit = 50
    elif raw.lower() == "none":
        limit = None
    else:
        try:
            limit = int(raw)
        except ValueError:
            print("  invalid — using 50")
            limit = 50

    print(f"\n  Task: {lb_id}  |  Limit: {limit if limit else 'all samples'}")
    return lb_id, limit


# ── step 3: confirm + run eval ───────────────────────────────────────────────

def step_run_eval(models: list[str], lb_id: str, limit: int | None) -> bool:
    header("STEP 3 — Run evaluation")

    print(f"\n  Models : {', '.join(models)}")
    print(f"  Task   : {lb_id}")
    print(f"  Limit  : {limit if limit else 'all'}")
    print(f"  Log dir: outputs/inspect/")

    if not confirm("Run eval now?"):
        print("  Skipping eval.")
        return False

    cmd = [
        PYTHON, "-m", "src.eval.run_inspect",
        "--lb-id", lb_id,
        "--models", ",".join(models),
    ]
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
    print(f"  Output : LongevityBench Design System/ui_kits/longevity_bench/public/data.json")

    if not confirm("Export now?"):
        print("  Skipping export. Dashboard not updated.")
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

    print("\n  Dashboard is a static site — needs a local HTTP server.")
    print(f"  Serve dir : {DASHBOARD_DIR}")
    print(f"  URL       : http://localhost:8765/")

    if not confirm("Start HTTP server now? (blocks terminal until Ctrl-C)"):
        print("\n  To serve later:")
        print(f'    cd "{DASHBOARD_DIR}"')
        print("    python3 -m http.server 8765")
        print("    open http://localhost:8765/")
        return

    import os
    os.chdir(DASHBOARD_DIR)
    print("\n  Server starting on http://localhost:8765/ — press Ctrl-C to stop\n")
    try:
        subprocess.run([PYTHON, "-m", "http.server", "8765"])
    except KeyboardInterrupt:
        print("\n  Server stopped.")


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n  LongevityBench Pipeline")
    print("  eval → export → dashboard\n")

    if not MODELS_YAML.exists():
        print(f"  ERROR: config/models.yaml not found at {MODELS_YAML}")
        sys.exit(1)

    with open(MODELS_YAML) as f:
        registry = yaml.safe_load(f)["models"]

    models = step_choose_models(registry)
    lb_id, limit = step_choose_task()
    eval_ok = step_run_eval(models, lb_id, limit)

    if eval_ok or LOG_DIR.exists():
        step_export()

    step_serve()

    header("Done")
    print("  Refresh http://localhost:8765/ to see updated results.\n")


if __name__ == "__main__":
    main()

"""Generate outputs/gap_analysis_report.md from exported data.json.

Usage:
    python -m src.analysis.gap_analysis \\
        --data "LongevityBench Design System/ui_kits/longevity_bench/public/data.json" \\
        --train data/task_a_senescence/processed/task_a_senescence_train.parquet \\
        --test  data/task_a_senescence/processed/task_a_senescence_test.parquet \\
        --out   outputs/gap_analysis_report.md
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
)
from scipy.stats import spearmanr

logger = logging.getLogger(__name__)

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_LETTER_RE  = re.compile(r"(?<![A-Za-z])([A-F])(?![A-Za-z])")

MODEL_DISPLAY = {
    "longevity_llm":     "L-LLM",
    "claude_sonnet":     "Claude Sonnet",
    "majority_baseline": "Majority",
    "random_baseline":   "Random",
}


# ── extraction helpers ────────────────────────────────────────────────────────

def _extract_letter(text: str | None) -> str | None:
    if not text:
        return None
    hits = _LETTER_RE.findall(str(text))
    return hits[-1] if hits else str(text).strip().upper()[:1] or None


def _extract_number(text: str | None) -> float | None:
    if not text:
        return None
    m = _NUMBER_RE.search(str(text))
    return float(m.group()) if m else None


# ── bootstrap CI ─────────────────────────────────────────────────────────────

def _bootstrap_ci(
    y_true: list, y_pred: list, metric_fn, n: int = 1000, alpha: float = 0.05
) -> tuple[float, float]:
    rng = np.random.default_rng(42)
    arr_t = np.array(y_true)
    arr_p = np.array(y_pred)
    scores = []
    for _ in range(n):
        idx = rng.integers(0, len(arr_t), size=len(arr_t))
        try:
            scores.append(metric_fn(arr_t[idx], arr_p[idx]))
        except Exception:
            pass
    if not scores:
        return (float("nan"), float("nan"))
    lo = float(np.percentile(scores, 100 * alpha / 2))
    hi = float(np.percentile(scores, 100 * (1 - alpha / 2)))
    return (lo, hi)


# ── per-format metrics ────────────────────────────────────────────────────────

def _mcq_metrics(
    gold: list[str], pred: list[str]
) -> dict[str, Any]:
    labels = sorted(set(gold) | set(pred))
    acc = accuracy_score(gold, pred)
    f1  = f1_score(gold, pred, average="macro", labels=labels, zero_division=0)
    bal = balanced_accuracy_score(gold, pred)
    ci_acc = _bootstrap_ci(gold, pred, accuracy_score)
    ci_f1  = _bootstrap_ci(gold, pred,
                           lambda t, p: f1_score(t, p, average="macro",
                                                 labels=labels, zero_division=0))
    cm = confusion_matrix(gold, pred, labels=labels).tolist()
    return {
        "n": len(gold), "labels": labels,
        "accuracy": round(acc, 4), "macro_f1": round(f1, 4),
        "balanced_accuracy": round(bal, 4),
        "ci_accuracy": [round(x, 4) for x in ci_acc],
        "ci_macro_f1": [round(x, 4) for x in ci_f1],
        "confusion_matrix": {"labels": labels, "matrix": cm},
    }


def _binary_metrics(gold: list[str], pred: list[str]) -> dict[str, Any]:
    labels = ["A", "B"]
    acc = accuracy_score(gold, pred)
    bal = balanced_accuracy_score(gold, pred)
    ci_acc = _bootstrap_ci(gold, pred, accuracy_score)
    class_acc: dict[str, float] = {}
    for lbl in labels:
        mask = [g == lbl for g in gold]
        if any(mask):
            class_acc[lbl] = round(
                sum(g == p for g, p, m in zip(gold, pred, mask) if m) / sum(mask), 4
            )
    return {
        "n": len(gold),
        "accuracy": round(acc, 4),
        "balanced_accuracy": round(bal, 4),
        "ci_accuracy": [round(x, 4) for x in ci_acc],
        "class_accuracy": class_acc,
    }


def _regression_metrics(gold: list[float], pred: list[float]) -> dict[str, Any]:
    g = np.array(gold)
    p = np.array(pred)
    mae  = float(np.mean(np.abs(g - p)))
    mdae = float(np.median(np.abs(g - p)))
    with np.errstate(invalid="ignore"):
        rho, pval = spearmanr(g, p)
    rho  = 0.0 if np.isnan(rho) else rho
    pval = 1.0 if np.isnan(pval) else pval
    sign_acc = float(np.mean(np.sign(g) == np.sign(p)))
    ci_mae = _bootstrap_ci(
        gold, pred, lambda t, pr: float(np.mean(np.abs(np.array(t) - np.array(pr))))
    )
    return {
        "n": len(gold),
        "mae": round(mae, 4), "median_ae": round(mdae, 4),
        "spearman_r": round(float(rho), 4), "spearman_p": round(float(pval), 4),
        "sign_accuracy": round(sign_acc, 4),
        "ci_mae": [round(x, 4) for x in ci_mae],
    }


# ── collect predictions from data.json ───────────────────────────────────────

def _collect(data: dict) -> dict[str, dict[str, dict]]:
    """Return nested: {model_id: {format: {gold:[], pred:[]}}}"""
    bucket: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {"gold": [], "pred": []}))
    for sample in data["samples"]:
        fmt = (sample.get("format") or "unknown").lower()
        gold_raw = sample.get("gold") or ""
        for model_id, cell in (sample.get("cells") or {}).items():
            pred_raw = cell.get("pred") or ""
            bucket[model_id][fmt]["gold"].append(gold_raw)
            bucket[model_id][fmt]["pred"].append(pred_raw)
    return bucket


# ── compute metrics table ─────────────────────────────────────────────────────

def compute_all_metrics(data: dict) -> dict[str, dict[str, dict]]:
    """Return {model_id: {format: metrics_dict}}."""
    bucket = _collect(data)
    results: dict[str, dict[str, dict]] = {}

    for model_id, fmt_data in bucket.items():
        results[model_id] = {}
        for fmt, pairs in fmt_data.items():
            gold_raw = pairs["gold"]
            pred_raw = pairs["pred"]

            if fmt in ("mcq",):
                gold = [_extract_letter(g) or g for g in gold_raw]
                pred = [_extract_letter(p) or p for p in pred_raw]
                results[model_id][fmt] = _mcq_metrics(gold, pred)

            elif fmt in ("binary", "pairwise"):
                gold = [_extract_letter(g) or g for g in gold_raw]
                pred = [_extract_letter(p) or p for p in pred_raw]
                results[model_id][fmt] = _binary_metrics(gold, pred)

            elif fmt in ("regression",):
                gold_f = [_extract_number(g) for g in gold_raw]
                pred_f = [_extract_number(p) for p in pred_raw]
                # drop pairs where parse failed
                valid = [(g, p) for g, p in zip(gold_f, pred_f) if g is not None and p is not None]
                if valid:
                    gv, pv = zip(*valid)
                    results[model_id][fmt] = _regression_metrics(list(gv), list(pv))
                    results[model_id][fmt]["parse_failures"] = len(gold_f) - len(valid)
                else:
                    results[model_id][fmt] = {"n": 0, "mae": None}

    return results


# ── dataset summary ───────────────────────────────────────────────────────────

def dataset_summary(train_path: Path | None, test_path: Path | None) -> dict:
    summary: dict[str, Any] = {}
    for split, path in [("train", train_path), ("test", test_path)]:
        if path and path.exists():
            df = pd.read_parquet(path)
            summary[split] = {
                "n": len(df),
                "formats": df["format"].value_counts().to_dict() if "format" in df.columns else {},
                "accessions": df["metadata"].apply(
                    lambda m: json.loads(m).get("acc_no") if isinstance(m, str) else (m or {}).get("acc_no")
                ).nunique() if "metadata" in df.columns else None,
            }
            if "format" in df.columns:
                import json as _json
                def get_tgt(row):
                    msgs = row["messages"]
                    if isinstance(msgs, str): msgs = _json.loads(msgs)
                    return msgs[-1]["content"]
                label_dist: dict[str, dict] = {}
                for fmt in df["format"].unique():
                    sub = df[df["format"] == fmt]
                    tgts = sub.apply(get_tgt, axis=1).value_counts().to_dict()
                    label_dist[fmt] = tgts
                summary[split]["label_dist"] = label_dist
    return summary


# ── markdown report ───────────────────────────────────────────────────────────

def _fmt_ci(ci: list | None) -> str:
    if not ci or any(np.isnan(x) for x in ci):
        return "—"
    return f"[{ci[0]:.3f}, {ci[1]:.3f}]"


def _fmt_cm(cm_info: dict) -> str:
    labels = cm_info["labels"]
    matrix = cm_info["matrix"]
    header = "| pred→ | " + " | ".join(labels) + " |"
    sep    = "|---|" + "---|" * len(labels)
    rows   = [header, sep]
    for i, lbl in enumerate(labels):
        row = f"| gold={lbl} | " + " | ".join(str(v) for v in matrix[i]) + " |"
        rows.append(row)
    return "\n".join(rows)


def render_report(
    metrics: dict[str, dict[str, dict]],
    ds: dict,
    generated_at: str,
) -> str:
    lines: list[str] = []
    a = lines.append

    a("# LongevityBench-X · Task A Senescence · Gap Analysis Report")
    a(f"\n_Generated: {generated_at}_\n")

    # ── dataset summary
    a("## 1. Dataset Summary\n")
    for split in ("train", "test"):
        if split not in ds:
            continue
        info = ds[split]
        a(f"### {split.title()} split")
        a(f"- Total samples: **{info['n']}**")
        fmt_str = ", ".join(f"{k}={v}" for k, v in sorted(info.get("formats", {}).items()))
        a(f"- Per-format: {fmt_str}")
        if info.get("accessions"):
            a(f"- GEO accessions: {info['accessions']}")
        if "label_dist" in info:
            a("- Label distributions:")
            for fmt, dist in sorted(info["label_dist"].items()):
                dist_str = ", ".join(f"{k}={v}" for k, v in sorted(dist.items()))
                a(f"  - `{fmt}`: {dist_str}")
        a("")

    a("**Split logic:** Train/test split by GEO accession — all samples from one study stay together. ")
    a("Prevents label leakage from shared batch effects and analysis pipelines.\n")

    # ── main results table
    a("## 2. Main Results\n")
    formats_present = sorted({fmt for m in metrics.values() for fmt in m})

    for fmt in formats_present:
        a(f"### Format: `{fmt}`\n")
        if fmt in ("mcq",):
            a("| Model | N | Accuracy | Macro F1 | Balanced Acc | CI (F1) |")
            a("|---|---|---|---|---|---|")
            for mid in ["longevity_llm", "claude_sonnet", "majority_baseline", "random_baseline"]:
                if mid not in metrics or fmt not in metrics[mid]:
                    continue
                m = metrics[mid][fmt]
                name = MODEL_DISPLAY.get(mid, mid)
                ci = _fmt_ci(m.get("ci_macro_f1"))
                a(f"| {name} | {m['n']} | {m['accuracy']:.3f} | {m['macro_f1']:.3f} | {m['balanced_accuracy']:.3f} | {ci} |")
            a("")
            # confusion matrices
            a("**Confusion matrices:**\n")
            for mid in ["longevity_llm", "claude_sonnet"]:
                if mid not in metrics or fmt not in metrics[mid]:
                    continue
                cm_info = metrics[mid][fmt].get("confusion_matrix")
                if cm_info:
                    a(f"_{MODEL_DISPLAY.get(mid, mid)}_\n")
                    a(_fmt_cm(cm_info))
                    a("")

        elif fmt in ("binary", "pairwise"):
            a("| Model | N | Accuracy | Balanced Acc | Acc(A) | Acc(B) | CI (Acc) |")
            a("|---|---|---|---|---|---|---|")
            for mid in ["longevity_llm", "claude_sonnet", "majority_baseline", "random_baseline"]:
                if mid not in metrics or fmt not in metrics[mid]:
                    continue
                m = metrics[mid][fmt]
                name = MODEL_DISPLAY.get(mid, mid)
                ca = m.get("class_accuracy", {})
                ci = _fmt_ci(m.get("ci_accuracy"))
                a(f"| {name} | {m['n']} | {m['accuracy']:.3f} | {m['balanced_accuracy']:.3f} | {ca.get('A','—')} | {ca.get('B','—')} | {ci} |")
            a("")

        elif fmt in ("regression",):
            a("| Model | N | MAE | Median AE | Spearman r | Sign Acc | CI (MAE) |")
            a("|---|---|---|---|---|---|---|")
            for mid in ["longevity_llm", "claude_sonnet", "majority_baseline", "random_baseline"]:
                if mid not in metrics or fmt not in metrics[mid]:
                    continue
                m = metrics[mid][fmt]
                name = MODEL_DISPLAY.get(mid, mid)
                if m.get("mae") is None:
                    a(f"| {name} | {m.get('n',0)} | — | — | — | — | — |")
                    continue
                ci = _fmt_ci(m.get("ci_mae"))
                a(f"| {name} | {m['n']} | {m['mae']:.3f} | {m['median_ae']:.3f} | {m['spearman_r']:.3f} | {m['sign_accuracy']:.3f} | {ci} |")
            a("")

    # ── failure analysis
    a("## 3. Failure Analysis\n")
    a("### MCQ — class-level errors")
    if "mcq" in formats_present:
        for mid in ["longevity_llm", "claude_sonnet"]:
            if mid not in metrics or "mcq" not in metrics[mid]:
                continue
            m = metrics[mid]["mcq"]
            cm_info = m.get("confusion_matrix")
            if not cm_info:
                continue
            labels = cm_info["labels"]
            matrix = np.array(cm_info["matrix"])
            name = MODEL_DISPLAY.get(mid, mid)
            a(f"\n**{name}:** most-confused pairs:")
            off_diag = [(matrix[i][j], labels[i], labels[j])
                        for i in range(len(labels)) for j in range(len(labels)) if i != j]
            off_diag.sort(reverse=True)
            for count, true_lbl, pred_lbl in off_diag[:3]:
                if count > 0:
                    a(f"- gold={true_lbl} predicted as {pred_lbl}: {count}×")

    a("\n### Regression — direction errors")
    if "regression" in formats_present:
        bucket = _collect({"samples": []})  # placeholder
        a("See confusion of sign (positive vs negative Log2FC) in sign_accuracy metric above.\n")

    a("\n### Binary — A/B prediction bias")
    if "binary" in formats_present:
        for mid in ["longevity_llm", "claude_sonnet", "majority_baseline", "random_baseline"]:
            if mid not in metrics or "binary" not in metrics[mid]:
                continue
            m = metrics[mid]["binary"]
            ca = m.get("class_accuracy", {})
            name = MODEL_DISPLAY.get(mid, mid)
            a(f"- **{name}**: class A acc={ca.get('A','—')}, class B acc={ca.get('B','—')}")
    a("")

    # ── baseline comparison
    a("## 4. Baseline Summary\n")
    a("| Baseline | MCQ acc | Binary acc | Regression MAE |")
    a("|---|---|---|---|")
    for mid in ["majority_baseline", "random_baseline"]:
        name = MODEL_DISPLAY.get(mid, mid)
        mcq_acc = metrics.get(mid, {}).get("mcq", {}).get("accuracy", "—")
        bin_acc = metrics.get(mid, {}).get("binary", {}).get("accuracy", "—")
        reg_mae = metrics.get(mid, {}).get("regression", {}).get("mae", "—")
        a(f"| {name} | {mcq_acc} | {bin_acc} | {reg_mae} |")
    a("")
    a("_Majority baseline uses per-format most-frequent label from training split._  ")
    a("_Random baseline draws uniformly from valid label set per format (A/B/C for MCQ, A/B for binary, 0 for regression)._\n")

    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path,
                        default=Path("LongevityBench Design System/ui_kits/longevity_bench/public/data.json"))
    parser.add_argument("--train", type=Path,
                        default=Path("data/task_a_senescence/processed/task_a_senescence_train.parquet"))
    parser.add_argument("--test", type=Path,
                        default=Path("data/task_a_senescence/processed/task_a_senescence_test.parquet"))
    parser.add_argument("--out", type=Path, default=Path("outputs/gap_analysis_report.md"))
    args = parser.parse_args()

    data = json.loads(args.data.read_text())
    ds = dataset_summary(
        args.train if args.train.exists() else None,
        args.test  if args.test.exists()  else None,
    )
    metrics = compute_all_metrics(data)

    report = render_report(metrics, ds, data.get("generated_at", "unknown"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    logger.info("report written → %s", args.out)

    # Print quick summary to stdout
    print("\n=== Quick Results ===")
    for fmt in ("mcq", "binary", "regression"):
        print(f"\n{fmt.upper()}:")
        for mid in ["longevity_llm", "claude_sonnet", "majority_baseline", "random_baseline"]:
            m = metrics.get(mid, {}).get(fmt)
            if not m:
                continue
            name = MODEL_DISPLAY.get(mid, mid)
            if fmt == "regression":
                val = f"MAE={m.get('mae','?')}"
            else:
                val = f"acc={m.get('accuracy','?')} f1={m.get('macro_f1','?')}"
            print(f"  {name:<20} {val}")


if __name__ == "__main__":
    main()

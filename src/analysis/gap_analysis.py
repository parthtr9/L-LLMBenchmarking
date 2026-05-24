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
    "longevity_llm":              "L-LLM",
    "longevity_llm_thinking":     "L-LLM (think)",
    "claude_sonnet":              "Claude Sonnet",
    "majority_baseline":          "Majority",
    "random_baseline":            "Random",
    "population_prior_baseline":  "Population Prior Prediction",
}

MODEL_ORDER = [
    "longevity_llm",
    "longevity_llm_thinking",
    "claude_sonnet",
    "majority_baseline",
    "random_baseline",
    "population_prior_baseline",
]


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
    pred_counts = {lbl: int(sum(p == lbl for p in pred)) for lbl in labels}
    gold_counts = {lbl: int(sum(g == lbl for g in gold)) for lbl in labels}
    pred_frac = {
        lbl: round(pred_counts[lbl] / len(pred), 4) if pred else 0.0
        for lbl in labels
    }
    gold_frac = {
        lbl: round(gold_counts[lbl] / len(gold), 4) if gold else 0.0
        for lbl in labels
    }
    # Positive = model over-predicts A relative to gold distribution.
    a_bias = pred_frac["A"] - gold_frac["A"]
    return {
        "n": len(gold),
        "accuracy": round(acc, 4),
        "balanced_accuracy": round(bal, 4),
        "ci_accuracy": [round(x, 4) for x in ci_acc],
        "class_accuracy": class_acc,
        "gold_distribution": gold_counts,
        "prediction_distribution": pred_counts,
        "prediction_fraction": pred_frac,
        "a_bias": round(a_bias, 4),
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


# ── task-group normalisation ──────────────────────────────────────────────────

def _normalize_task_group(display_group: str | None, lb_id: str | None = None) -> str:
    if display_group:
        if display_group.startswith("Lipidomics"):
            return "Lipidomics"
        return display_group
    # Fall back to lb_id prefix
    if lb_id:
        if lb_id.startswith("LB-SEN"):
            return "Senescence Perturbation"
        if lb_id.startswith("LB-LIP"):
            return "Lipidomics"
        if lb_id.startswith("LB-MET"):
            return "Metabolite Prediction"
    return "Other"


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


def _collect_by_task(data: dict) -> dict[str, dict[str, dict[str, dict]]]:
    """Return nested: {task_group: {model_id: {format: {gold:[], pred:[]}}}}"""
    outer: dict[str, Any] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: {"gold": [], "pred": []}))
    )
    for sample in data["samples"]:
        meta = sample.get("metadata") or {}
        task_group = _normalize_task_group(meta.get("display_group"), sample.get("lb_id"))
        fmt = (sample.get("format") or "unknown").lower()
        gold_raw = sample.get("gold") or ""
        for model_id, cell in (sample.get("cells") or {}).items():
            pred_raw = cell.get("pred") or ""
            outer[task_group][model_id][fmt]["gold"].append(gold_raw)
            outer[task_group][model_id][fmt]["pred"].append(pred_raw)
    return outer


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

def dataset_summary(train_path: Path | list[Path] | None, test_path: Path | list[Path] | None) -> dict:
    def _load(paths: Path | list[Path] | None) -> "pd.DataFrame | None":
        if paths is None:
            return None
        if isinstance(paths, Path):
            paths = [paths]
        frames = [pd.read_parquet(p) for p in paths if p and p.exists()]
        return pd.concat(frames, ignore_index=True) if frames else None

    summary: dict[str, Any] = {}
    for split, df in [("train", _load(train_path)), ("test", _load(test_path))]:
        if df is not None:
            def get_accession(meta: Any) -> str | None:
                if isinstance(meta, str):
                    meta = json.loads(meta)
                if not isinstance(meta, dict):
                    return None
                return meta.get("accession") or meta.get("acc_no") or meta.get("Acc_no")

            summary[split] = {
                "n": len(df),
                "formats": df["format"].value_counts().to_dict() if "format" in df.columns else {},
                "accessions": df["metadata"].apply(
                    get_accession
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


def _ordered_models(metrics: dict[str, dict[str, dict]]) -> list[str]:
    ordered = [mid for mid in MODEL_ORDER if mid in metrics]
    ordered.extend(sorted(mid for mid in metrics if mid not in ordered))
    return ordered


def _format_label(fmt: str) -> str:
    if fmt == "binary":
        return "binary/significance"
    return fmt


def _render_coverage_table(metrics: dict[str, dict[str, dict]], formats: list[str]) -> list[str]:
    lines = ["## 2. Evaluation Coverage\n"]
    header = "| Model | " + " | ".join(_format_label(fmt) for fmt in formats) + " |"
    sep = "|---|" + "---|" * len(formats)
    lines.extend([header, sep])
    for mid in _ordered_models(metrics):
        row = [MODEL_DISPLAY.get(mid, mid)]
        for fmt in formats:
            n = metrics.get(mid, {}).get(fmt, {}).get("n")
            row.append(str(n) if n is not None else "—")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    return lines


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

    # ── coverage + main results table
    formats_present = sorted({fmt for m in metrics.values() for fmt in m})
    lines.extend(_render_coverage_table(metrics, formats_present))

    a("## 3. Main Results\n")

    for fmt in formats_present:
        a(f"### Format: `{_format_label(fmt)}`\n")
        if fmt in ("mcq",):
            a("| Model | N | Accuracy | Macro F1 | Balanced Acc | CI (F1) |")
            a("|---|---|---|---|---|---|")
            for mid in _ordered_models(metrics):
                if mid not in metrics or fmt not in metrics[mid]:
                    continue
                m = metrics[mid][fmt]
                name = MODEL_DISPLAY.get(mid, mid)
                ci = _fmt_ci(m.get("ci_macro_f1"))
                a(f"| {name} | {m['n']} | {m['accuracy']:.3f} | {m['macro_f1']:.3f} | {m['balanced_accuracy']:.3f} | {ci} |")
            a("")
            # confusion matrices
            a("**Confusion matrices:**\n")
            for mid in _ordered_models(metrics):
                if mid not in metrics or fmt not in metrics[mid]:
                    continue
                cm_info = metrics[mid][fmt].get("confusion_matrix")
                if cm_info:
                    a(f"_{MODEL_DISPLAY.get(mid, mid)}_\n")
                    a(_fmt_cm(cm_info))
                    a("")

        elif fmt == "binary":
            a("| Model | N | Accuracy | Balanced Acc | Acc(A) | Acc(B) | CI (Acc) |")
            a("|---|---|---|---|---|---|---|")
            for mid in _ordered_models(metrics):
                if mid not in metrics or fmt not in metrics[mid]:
                    continue
                m = metrics[mid][fmt]
                name = MODEL_DISPLAY.get(mid, mid)
                ca = m.get("class_accuracy", {})
                ci = _fmt_ci(m.get("ci_accuracy"))
                a(f"| {name} | {m['n']} | {m['accuracy']:.3f} | {m['balanced_accuracy']:.3f} | {ca.get('A','—')} | {ca.get('B','—')} | {ci} |")
            a("")

        elif fmt == "pairwise":
            a("| Model | N | Accuracy | Balanced Acc | Pred A% | Pred B% | A-bias | CI (Acc) |")
            a("|---|---|---|---|---|---|---|---|")
            for mid in _ordered_models(metrics):
                if mid not in metrics or fmt not in metrics[mid]:
                    continue
                m = metrics[mid][fmt]
                name = MODEL_DISPLAY.get(mid, mid)
                pf = m.get("prediction_fraction", {})
                ci = _fmt_ci(m.get("ci_accuracy"))
                pred_a = pf.get("A", "—")
                pred_b = pf.get("B", "—")
                if isinstance(pred_a, float):
                    pred_a = f"{100 * pred_a:.1f}%"
                if isinstance(pred_b, float):
                    pred_b = f"{100 * pred_b:.1f}%"
                a(f"| {name} | {m['n']} | {m['accuracy']:.3f} | {m['balanced_accuracy']:.3f} | {pred_a} | {pred_b} | {m.get('a_bias','—')} | {ci} |")
            a("")

        elif fmt in ("regression",):
            a("| Model | N | MAE | Median AE | Spearman r | Sign Acc | CI (MAE) |")
            a("|---|---|---|---|---|---|---|")
            for mid in _ordered_models(metrics):
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
    a("## 4. Failure Analysis\n")
    a("### MCQ — class-level errors")
    if "mcq" in formats_present:
        for mid in _ordered_models(metrics):
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

    a("\n### Binary/significance — class-wise accuracy")
    if "binary" in formats_present:
        for mid in _ordered_models(metrics):
            if mid not in metrics or "binary" not in metrics[mid]:
                continue
            m = metrics[mid]["binary"]
            ca = m.get("class_accuracy", {})
            name = MODEL_DISPLAY.get(mid, mid)
            a(f"- **{name}**: class A acc={ca.get('A','—')}, class B acc={ca.get('B','—')}")
    a("")

    a("### Pairwise — A/B prediction bias")
    if "pairwise" in formats_present:
        for mid in _ordered_models(metrics):
            if mid not in metrics or "pairwise" not in metrics[mid]:
                continue
            m = metrics[mid]["pairwise"]
            pf = m.get("prediction_fraction", {})
            name = MODEL_DISPLAY.get(mid, mid)
            pred_a = pf.get("A")
            pred_b = pf.get("B")
            pred_a_str = f"{100 * pred_a:.1f}%" if isinstance(pred_a, float) else "—"
            pred_b_str = f"{100 * pred_b:.1f}%" if isinstance(pred_b, float) else "—"
            a(f"- **{name}**: predicted A={pred_a_str}, predicted B={pred_b_str}, A-bias={m.get('a_bias','—')}")
    a("")

    if "regression" in formats_present:
        a("### Regression — direction errors")
        a("See sign_accuracy in the regression metrics table above.\n")

    # ── baseline comparison
    a("## 5. Baseline Summary\n")
    baseline_formats = [fmt for fmt in ("mcq", "binary", "pairwise", "regression") if fmt in formats_present]
    header_names = {
        "mcq": "MCQ acc",
        "binary": "Binary acc",
        "pairwise": "Pairwise acc",
        "regression": "Regression MAE",
    }
    a("| Baseline | " + " | ".join(header_names[fmt] for fmt in baseline_formats) + " |")
    a("|---|" + "---|" * len(baseline_formats))
    for mid in ["majority_baseline", "random_baseline", "population_prior_baseline"]:
        if mid not in metrics:
            continue
        name = MODEL_DISPLAY.get(mid, mid)
        vals = []
        for fmt in baseline_formats:
            key = "mae" if fmt == "regression" else "accuracy"
            vals.append(str(metrics.get(mid, {}).get(fmt, {}).get(key, "—")))
        a("| " + " | ".join([name] + vals) + " |")
    a("")
    a("_Majority baseline uses per-format most-frequent label from training split._  ")
    a("_Random baseline draws uniformly from valid label set per format (A/B/C for MCQ, A/B for binary/pairwise)._  ")
    a("_Population Prior Prediction baseline samples regression age from US Census 2025 population estimates conditioned on donor sex (no train labels used)._\n")

    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path,
                        default=Path("LongevityBench Design System/ui_kits/longevity_bench/public/data.json"))
    parser.add_argument("--train", type=Path, action="append", default=[],
                        help="Train parquet path(s). Repeat flag for multiple datasets.")
    parser.add_argument("--test", type=Path, action="append", default=[],
                        help="Test parquet path(s). Repeat flag for multiple datasets.")
    parser.add_argument("--out", type=Path, default=Path("outputs/gap_analysis_report.md"))
    args = parser.parse_args()

    # Fall back to Task A defaults when no paths supplied (standalone usage)
    train_paths: list[Path] = args.train or [
        Path("data/task_a_senescence/processed/task_a_senescence_train.parquet")
    ]
    test_paths: list[Path] = args.test or [
        Path("data/task_a_senescence/processed/task_a_senescence_test.parquet")
    ]

    data = json.loads(args.data.read_text())
    ds = dataset_summary(train_paths, test_paths)
    metrics = compute_all_metrics(data)

    report = render_report(metrics, ds, data.get("generated_at", "unknown"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    logger.info("report written → %s", args.out)

    _PUBLIC_DIR = Path("LongevityBench Design System/ui_kits/longevity_bench/public")
    _PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    (_PUBLIC_DIR / "gap_analysis_report.md").write_text(report, encoding="utf-8")
    logger.info("report mirrored → %s", _PUBLIC_DIR / "gap_analysis_report.md")

    # Per-task metrics for dashboard task-switcher filtering
    task_buckets = _collect_by_task(data)
    tasks_payload: dict[str, Any] = {}
    for task_group, task_data_bucket in task_buckets.items():
        task_metrics: dict[str, dict[str, dict]] = {}
        for model_id, fmt_data in task_data_bucket.items():
            task_metrics[model_id] = {}
            # Reuse the same per-format metric functions via a synthetic data dict
            synthetic = {"samples": []}  # not used directly — compute inline
            for fmt, pairs in fmt_data.items():
                gold_raw = pairs["gold"]
                pred_raw = pairs["pred"]
                if fmt in ("mcq",):
                    gold = [_extract_letter(g) or g for g in gold_raw]
                    pred = [_extract_letter(p) or p for p in pred_raw]
                    task_metrics[model_id][fmt] = _mcq_metrics(gold, pred)
                elif fmt in ("binary", "pairwise"):
                    gold = [_extract_letter(g) or g for g in gold_raw]
                    pred = [_extract_letter(p) or p for p in pred_raw]
                    task_metrics[model_id][fmt] = _binary_metrics(gold, pred)
                elif fmt in ("regression",):
                    gold_f = [_extract_number(g) for g in gold_raw]
                    pred_f = [_extract_number(p) for p in pred_raw]
                    valid = [(g, p) for g, p in zip(gold_f, pred_f) if g is not None and p is not None]
                    if valid:
                        gv, pv = zip(*valid)
                        task_metrics[model_id][fmt] = _regression_metrics(list(gv), list(pv))
                        task_metrics[model_id][fmt]["parse_failures"] = len(gold_f) - len(valid)
                    else:
                        task_metrics[model_id][fmt] = {"n": 0, "mae": None}
        tasks_payload[task_group] = {
            "metrics": task_metrics,
            "model_display": MODEL_DISPLAY,
            "model_order": MODEL_ORDER,
        }
        logger.info("per-task metrics computed for: %s (%d models)", task_group, len(task_metrics))

    # Also write structured JSON for the dashboard UI
    payload = {
        "generated_at": data.get("generated_at", "unknown"),
        "dataset": ds,
        "model_display": MODEL_DISPLAY,
        "model_order": MODEL_ORDER,
        "metrics": metrics,
        "tasks": tasks_payload,
    }
    json_path = args.out.with_suffix(".json")
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (_PUBLIC_DIR / "gap_analysis_data.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("data JSON → %s", json_path)

    # Print quick summary to stdout
    print("\n=== Quick Results ===")
    for fmt in ("mcq", "binary", "pairwise", "regression"):
        print(f"\n{fmt.upper()}:")
        for mid in _ordered_models(metrics):
            m = metrics.get(mid, {}).get(fmt)
            if not m:
                continue
            name = MODEL_DISPLAY.get(mid, mid)
            if fmt == "regression":
                val = f"MAE={m.get('mae','?')}"
            elif fmt == "mcq":
                val = f"acc={m.get('accuracy','?')} macro_f1={m.get('macro_f1','?')} bal_acc={m.get('balanced_accuracy','?')}"
            elif fmt == "pairwise":
                val = f"acc={m.get('accuracy','?')} bal_acc={m.get('balanced_accuracy','?')} a_bias={m.get('a_bias','?')}"
            else:
                val = f"acc={m.get('accuracy','?')} bal_acc={m.get('balanced_accuracy','?')}"
            print(f"  {name:<20} {val}")


if __name__ == "__main__":
    main()

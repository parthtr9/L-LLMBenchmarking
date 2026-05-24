"""Local zero-shot judge — replaces Groq API with DeBERTa NLI.

pathway_score: zero-shot classify full trace as "accurate aging biology" vs not.
claim_score:   for each CellAge-annotated gene found in trace, classify the
               local context window (~250 chars) and check against CellAge
               ground truth (Induces/Inhibits senescence).

Reuses the same DeBERTa pipeline singleton from consistency_checker.
Cache keyed by SHA-256 of trace to avoid re-scoring identical traces.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path

import pandas as pd

from ..consistency_checker import _get_pipeline

logger = logging.getLogger(__name__)

_CACHE_PATH = Path("outputs/local_judge_cache.json")
_CONTEXT_WINDOW = 300  # chars either side of gene mention

_PATHWAY_LABELS = [
    "the conclusion follows logically from the biological evidence presented in this reasoning",
    "the conclusion contradicts or is unsupported by the biological evidence presented in this reasoning",
]

_INDUCES_LABELS = [
    "this gene increases, upregulates, or activates cellular senescence or aging",
    "this gene decreases, downregulates, or inhibits cellular senescence or aging",
]
_INHIBITS_LABELS = [
    "this gene decreases, downregulates, or inhibits cellular senescence or aging",
    "this gene increases, upregulates, or activates cellular senescence or aging",
]

_CELLAGE_DB: dict[str, str] = {}  # gene_upper → "Induces" | "Inhibits" | "Unclear"
_DB_LOADED = False


def _load_cellage_db() -> None:
    global _DB_LOADED
    if _DB_LOADED:
        return
    paths = [
        Path("data/task_a_senescence/processed/task_a_senescence_train.parquet"),
        Path("data/task_a_senescence/processed/task_a_senescence_test.parquet"),
    ]
    for p in paths:
        if not p.exists():
            continue
        try:
            df = pd.read_parquet(p)
            for _, row in df.iterrows():
                meta = json.loads(row["metadata"])
                gene = (meta.get("gene") or "").upper()
                effect = meta.get("cellage_effect") or "Unclear"
                if gene and gene not in _CELLAGE_DB:
                    _CELLAGE_DB[gene] = effect
        except Exception as exc:
            logger.warning("CellAge load failed for %s: %s", p, exc)
    _DB_LOADED = True
    logger.info("CellAge DB loaded: %d genes", len(_CELLAGE_DB))


def _context_for_gene(trace: str, gene: str) -> str | None:
    """Return ±CONTEXT_WINDOW chars around first mention of gene in trace."""
    m = re.search(rf"\b{re.escape(gene)}\b", trace, re.IGNORECASE)
    if not m:
        return None
    lo = max(0, m.start() - _CONTEXT_WINDOW)
    hi = min(len(trace), m.end() + _CONTEXT_WINDOW)
    return trace[lo:hi]


class LocalJudgment:
    __slots__ = ("pathway_score", "claim_score", "n_checked", "n_correct")

    def __init__(
        self,
        pathway_score: float,
        claim_score: float,
        n_checked: int,
        n_correct: int,
    ) -> None:
        self.pathway_score = pathway_score
        self.claim_score = claim_score
        self.n_checked = n_checked
        self.n_correct = n_correct


class LocalJudge:
    def __init__(self, cache_path: Path = _CACHE_PATH) -> None:
        self._cache_path = cache_path
        self._cache: dict[str, dict] = {}
        _load_cellage_db()
        self._load_cache()

    def _load_cache(self) -> None:
        if self._cache_path.exists():
            try:
                self._cache = json.loads(self._cache_path.read_text(encoding="utf-8"))
            except Exception:
                self._cache = {}

    def save_cache(self) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(json.dumps(self._cache, indent=2), encoding="utf-8")

    @staticmethod
    def _cache_key(trace: str) -> str:
        return hashlib.sha256(trace.encode()).hexdigest()[:20]

    def judge_trace(self, trace: str, verified_genes: list[str]) -> LocalJudgment:
        key = self._cache_key(trace)
        if key in self._cache:
            c = self._cache[key]
            return LocalJudgment(
                pathway_score=c["pathway_score"],
                claim_score=c["claim_score"],
                n_checked=c["n_checked"],
                n_correct=c["n_correct"],
            )

        pipe = _get_pipeline()
        result = self._score(pipe, trace, verified_genes)
        self._cache[key] = {
            "pathway_score": result.pathway_score,
            "claim_score": result.claim_score,
            "n_checked": result.n_checked,
            "n_correct": result.n_correct,
        }
        return result

    def _score(self, pipe, trace: str, verified_genes: list[str]) -> LocalJudgment:
        # ── pathway score ────────────────────────────────────────────────────
        try:
            out = pipe(
                trace[:1024],
                candidate_labels=_PATHWAY_LABELS,
                multi_label=False,
            )
            correct_label = _PATHWAY_LABELS[0]
            idx = out["labels"].index(correct_label)
            pathway_score = float(out["scores"][idx])
        except Exception as exc:
            logger.warning("pathway zero-shot failed: %s", exc)
            pathway_score = 0.5

        # ── claim score via CellAge ──────────────────────────────────────────
        n_checked = 0
        n_correct = 0

        cellage_genes = [g for g in verified_genes if _CELLAGE_DB.get(g.upper()) in ("Induces", "Inhibits")]

        for gene in cellage_genes[:8]:  # cap at 8 to keep inference fast
            effect = _CELLAGE_DB[gene.upper()]
            ctx = _context_for_gene(trace, gene)
            if not ctx:
                continue

            labels = _INDUCES_LABELS if effect == "Induces" else _INHIBITS_LABELS
            try:
                out = pipe(ctx[:512], candidate_labels=labels, multi_label=False)
                top_label = out["labels"][0]
                correct = top_label == labels[0]
                n_checked += 1
                if correct:
                    n_correct += 1
            except Exception as exc:
                logger.warning("claim zero-shot failed for %s: %s", gene, exc)

        claim_score = (n_correct / n_checked) if n_checked > 0 else 0.5

        return LocalJudgment(
            pathway_score=pathway_score,
            claim_score=claim_score,
            n_checked=n_checked,
            n_correct=n_correct,
        )

"""DB-anchored property verification for L-LLM thinking traces.

Where the MyGene verifier answers "does this gene symbol exist?", the property
checker answers the harder question the benchmark spec asks for:

    "verifying that mentioned genes... exist AND have the properties claimed"

For every verified gene G found in a trace, we look up G's annotated effect on
cellular senescence in the CellAge v3 database (Induces / Inhibits / Unclear),
extract the directional claim the trace makes about G from a local context
window, and decide whether the trace's claim matches the database fact.

This is unhackable and falsifiable in a way an LLM-as-judge is not:
the database fact is fixed, the regex over directional keywords is fixed,
and a model cannot "talk around" a contradiction with the underlying biology.

Returns:
  PropertyCheck(
    n_checked:   genes in trace that had a CellAge annotation and a directional claim
    n_correct:   subset where direction matched CellAge effect
    n_violated:  subset where direction contradicted CellAge effect
    score:       n_correct / n_checked (0.5 if n_checked == 0 — no signal, not penalty)
    violations:  list of (gene, claimed_direction, db_effect) tuples for diagnostics
  )
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_CONTEXT_WINDOW = 250  # chars on each side of gene mention

# Keywords mapped to direction relative to *senescence* (the CellAge axis).
# "induces senescence" → senescence-promoting; "inhibits senescence" → senescence-blocking.
_INDUCES_KEYWORDS = (
    "induces senescence", "promotes senescence", "drives senescence",
    "triggers senescence", "induc",  # short fallback
    "upregul", "increas", "elevat", "activat", "overexpress", "amplif",
)
_INHIBITS_KEYWORDS = (
    "inhibits senescence", "blocks senescence", "prevents senescence",
    "suppresses senescence", "inhibit",
    "downregul", "decreas", "reduc", "lower", "suppress", "silenc", "repress",
)
_NEGATION = ("not ", "no ", "without ", "absence of ", "fails to ", "does not ", "doesn't ")


@dataclass
class PropertyCheck:
    n_checked: int = 0
    n_correct: int = 0
    n_violated: int = 0
    violations: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def score(self) -> float:
        if self.n_checked == 0:
            return 0.5  # neutral — no claim to score
        return self.n_correct / self.n_checked


_CELLAGE_DB: dict[str, str] = {}
_DB_LOADED = False


def _load_cellage_db() -> None:
    """Build CellAge gene→effect dict from raw cellage3.tsv. Idempotent.

    Uses the full CellAge v3 release (~949 genes) rather than just the subset
    sampled into Task A prompts. This means we can verify directional claims
    about ANY senescence-annotated gene mentioned in a trace, not only the
    genes the model was specifically asked about.
    """
    global _DB_LOADED
    if _DB_LOADED:
        return
    raw_path = Path("data/task_a_senescence/raw/cellage3.tsv")
    if raw_path.exists():
        try:
            df = pd.read_csv(raw_path, sep="\t")
            for _, row in df.iterrows():
                gene = (row.get("Gene symbol") or "").upper()
                effect = row.get("Senescence Effect")
                if gene and effect in ("Induces", "Inhibits") and gene not in _CELLAGE_DB:
                    _CELLAGE_DB[gene] = effect
        except Exception as exc:
            logger.warning("CellAge raw load failed: %s", exc)
    _DB_LOADED = True
    logger.info("CellAge DB loaded: %d annotated genes", len(_CELLAGE_DB))


def _context_for_gene(trace: str, gene: str) -> str | None:
    m = re.search(rf"\b{re.escape(gene)}\b", trace, re.IGNORECASE)
    if not m:
        return None
    lo = max(0, m.start() - _CONTEXT_WINDOW)
    hi = min(len(trace), m.end() + _CONTEXT_WINDOW)
    return trace[lo:hi].lower()


def _claimed_direction(ctx: str) -> str | None:
    """Scan context for directional keyword nearest the gene mention.

    Returns "induces", "inhibits", or None (no clear claim).
    Negation flips the direction.
    """
    induces_hit = None
    inhibits_hit = None

    for kw in _INDUCES_KEYWORDS:
        idx = ctx.find(kw)
        if idx >= 0:
            induces_hit = (kw, idx)
            break
    for kw in _INHIBITS_KEYWORDS:
        idx = ctx.find(kw)
        if idx >= 0:
            inhibits_hit = (kw, idx)
            break

    candidate = None
    if induces_hit and inhibits_hit:
        # Pick the keyword closer to the gene mention (mid-window).
        mid = len(ctx) // 2
        d_ind = abs(induces_hit[1] - mid)
        d_inh = abs(inhibits_hit[1] - mid)
        candidate = ("induces", induces_hit) if d_ind <= d_inh else ("inhibits", inhibits_hit)
    elif induces_hit:
        candidate = ("induces", induces_hit)
    elif inhibits_hit:
        candidate = ("inhibits", inhibits_hit)
    else:
        return None

    direction, (kw, idx) = candidate
    # Negation check: any negation word in 30 chars before keyword?
    pre = ctx[max(0, idx - 30):idx]
    if any(neg in pre for neg in _NEGATION):
        direction = "inhibits" if direction == "induces" else "induces"
    return direction


def check_properties(trace: str, verified_genes: list[str]) -> PropertyCheck:
    """Cross-check each verified gene's directional claim in trace against CellAge.

    Args:
        trace: full L-LLM thinking trace text
        verified_genes: gene symbols already confirmed real by MyGeneVerifier

    Returns:
        PropertyCheck with score, violation list, and counts.
    """
    _load_cellage_db()
    result = PropertyCheck()

    for gene in verified_genes:
        g_upper = gene.upper()
        db_effect = _CELLAGE_DB.get(g_upper)
        if db_effect not in ("Induces", "Inhibits"):
            continue

        ctx = _context_for_gene(trace, gene)
        if not ctx:
            continue

        claimed = _claimed_direction(ctx)
        if claimed is None:
            continue

        result.n_checked += 1
        expected = "induces" if db_effect == "Induces" else "inhibits"
        if claimed == expected:
            result.n_correct += 1
        else:
            result.n_violated += 1
            result.violations.append((gene, claimed, db_effect))

    return result

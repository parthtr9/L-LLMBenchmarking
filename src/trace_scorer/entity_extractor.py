"""Extract gene symbols from L-LLM thinking traces.

Multi-species extractor — directly addresses a failure mode flagged in the
benchmark spec: "regex over capitalized tokens fails the moment a model stops
capitalizing, or the moment we evaluate on murine and C. elegans genes whose
symbols are not capitalized."

Three patterns are matched in parallel and union'd:

  HUMAN/zebrafish/yeast    UPPER          FOXO3, TP53, MTOR
  C. elegans / fungal      lower-hyphen   daf-2, age-1, clk-1
  Mouse / rat              Title          Trp53, Igf1r, Sirt6

Token candidates are stoplist-filtered and union-de-duplicated before being
handed to MyGeneVerifier, which queries 6-species namespace
(human/mouse/rat/fly/c_elegans/yeast). The verifier — not the extractor —
decides whether a token is a real gene.
"""

from __future__ import annotations

import re

# Human / zebrafish / yeast / general UPPERCASE symbol: 2-10 uppercase chars
_HUMAN_GENE_RE = re.compile(r'\b([A-Z][A-Z0-9]{1,9})\b')

# C. elegans (and many fungal) gene symbol: lower-hyphen-digit (daf-2, age-1, clk-1, eat-2)
_CELEGANS_GENE_RE = re.compile(r'\b([a-z]{2,4}-\d+[a-z]?)\b')

# Mouse / rat Title-case symbol: 1 upper + 1-9 lower/digit (Trp53, Igf1r, Sirt6, Foxo3)
# Filtered later by mygene; this regex over-matches common English words intentionally
_MOUSE_GENE_RE = re.compile(r'\b([A-Z][a-z0-9]{1,9})\b')

# Tokens that look like gene symbols but are not
_STOPWORDS: frozenset[str] = frozenset({
    "A", "B", "C", "D", "E", "F", "G", "I",
    "THE", "AND", "OR", "NOT", "BUT", "FOR", "WITH", "IN", "ON", "AT",
    "TO", "FROM", "BY", "AS", "IS", "ARE", "WAS", "WERE", "BE", "BEEN",
    "HAVE", "HAS", "HAD", "DO", "DOES", "DID", "WILL", "WOULD", "SHALL",
    "SHOULD", "MAY", "MIGHT", "MUST", "CAN", "COULD", "NO", "YES", "SO",
    "IF", "THEN", "ELSE", "WHEN", "WHERE", "HOW", "WHAT", "WHO", "WHY",
    "ALL", "BOTH", "EACH", "FEW", "MORE", "OTHER", "SOME", "SUCH", "THAN",
    "TOO", "VERY", "ALSO", "AFTER", "BEFORE", "WHILE", "SINCE", "UNTIL",
    "RNA", "DNA", "PCR", "GEO", "OIS", "DDIS", "REP", "IMR", "HFF",
    "LOG", "FC", "SD", "CI", "MCQ", "LB", "SEN", "UP", "DOWN",
    "LIMMA", "DEG", "DEGS", "RNASEQ", "MRNA", "QPCR", "CHIP",
    "PI", "SEM", "MAE", "AUC", "ROC", "HR", "OR", "RR", "WT",
    "KO", "OE", "KD", "CKO", "GOF", "LOF", "SNP", "CNV", "TPM", "FPKM",
})

# Title-case English words that look like mouse genes — filtered before sending to mygene
# (saves API quota and false positives). The verifier would reject them anyway, but pre-filtering
# keeps the candidate set clean for downstream property checks.
_TITLE_STOPWORDS: frozenset[str] = frozenset({
    "The", "And", "But", "For", "With", "From", "Into", "Onto", "Upon",
    "This", "That", "These", "Those", "There", "Their", "They", "Them",
    "When", "Where", "What", "Which", "While", "Whose", "Whom",
    "Cell", "Cells", "Gene", "Genes", "Type", "Types", "Study", "Studies",
    "Data", "Result", "Results", "Model", "Models", "Test", "Tests",
    "Group", "Groups", "Level", "Levels", "Value", "Values",
    "Figure", "Table", "Section", "Note", "Method", "Methods",
    "Step", "Steps", "Case", "Cases", "Time", "Times", "Day", "Days",
    "Week", "Weeks", "Year", "Years", "Hour", "Hours", "Minute", "Minutes",
    "Mouse", "Rat", "Human", "Yeast", "Fly", "Worm", "Cell", "Tissue",
    "Both", "Each", "All", "Some", "Most", "Many", "Few",
    "Yes", "No", "True", "False", "None",
    "Page", "Line", "Row", "Column", "Index",
})


def _filter_human(token: str) -> bool:
    return token not in _STOPWORDS and len(token) >= 2


def _filter_celegans(token: str) -> bool:
    # daf-2, age-1 — keep all. Stoplist is uppercase-only so no clash.
    return True


def _filter_mouse(token: str) -> bool:
    return token not in _TITLE_STOPWORDS and len(token) >= 3


def extract_gene_candidates(trace: str) -> list[str]:
    """Return unique gene-symbol candidates across human, C. elegans, and mouse patterns.

    Filters obvious stopwords; does NOT verify against any database. Verification
    is delegated to MyGeneVerifier, which queries the appropriate species namespace.
    """
    seen: set[str] = set()
    result: list[str] = []

    for token in _HUMAN_GENE_RE.findall(trace):
        if _filter_human(token) and token not in seen:
            seen.add(token)
            result.append(token)

    for token in _CELEGANS_GENE_RE.findall(trace):
        if _filter_celegans(token) and token not in seen:
            seen.add(token)
            result.append(token)

    for token in _MOUSE_GENE_RE.findall(trace):
        if _filter_mouse(token) and token not in seen:
            seen.add(token)
            result.append(token)

    return result

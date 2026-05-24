"""Extract gene symbols from L-LLM thinking traces."""

from __future__ import annotations

import re

# Human gene symbol: starts uppercase, 2-10 chars, letters+digits
_HUMAN_GENE_RE = re.compile(r'\b([A-Z][A-Z0-9]{1,9})\b')

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
    "LOG", "FC", "SD", "CI", "MCQ", "LB", "SEN", "MCQ", "UP", "DOWN",
    "LIMMA", "DEG", "DEGS", "RNAseq", "MRNA", "qPCR", "ChIP",
    "PI", "SEM", "MAE", "AUC", "ROC", "HR", "OR", "RR", "CI", "WT",
    "KO", "OE", "KD", "CKO", "GOF", "LOF", "SNP", "CNV",
})


def extract_gene_candidates(trace: str) -> list[str]:
    """Return unique uppercase gene-symbol candidates from a trace string.

    Filters stopwords and very short/long tokens. Does NOT hit any API —
    callers must verify candidates against NCBI.
    """
    seen: set[str] = set()
    result: list[str] = []
    for token in _HUMAN_GENE_RE.findall(trace):
        if token in _STOPWORDS:
            continue
        if token not in seen:
            seen.add(token)
            result.append(token)
    return result

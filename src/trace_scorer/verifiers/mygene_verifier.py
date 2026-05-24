"""Verify gene/protein symbol candidates via mygene.info batch lookup.

Replaces the old NCBI eutils verifier. Uses the synchronous mygene client
(run in a thread executor) to batch-query across multiple species at once.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import mygene

logger = logging.getLogger(__name__)

_CACHE_PATH = Path("outputs/mygene_cache.json")

_STOPLIST: frozenset[str] = frozenset({
    "DNA", "RNA", "PCR", "GEO", "NCBI", "API", "LLM", "AI", "ML",
    "KEGG", "GO", "MP", "CSV", "JSON", "HTTP", "URL", "ID", "QC",
    "MCQ", "LB", "OIS", "DDIS", "REP", "FC", "SD", "CI", "MAE",
    "AUC", "ROC", "HR", "OR", "RR", "WT", "KO", "OE", "KD", "CKO",
    "GOF", "LOF", "SNP", "CNV", "DEG", "MRNA", "ChIP", "SEM",
})

_SPECIES = "9606,10090,10116,7227,6239,4932"  # human,mouse,rat,fruitfly,c_elegans,yeast
_mg = mygene.MyGeneInfo()


def _is_valid_candidate(token: str) -> bool:
    if len(token) < 2:
        return False
    if token.upper() in _STOPLIST:
        return False
    if token.isdigit():
        return False
    return True


def _querymany_sync(tokens: list[str]) -> list[dict[str, Any]]:
    return _mg.querymany(
        tokens,
        scopes="symbol,alias",
        species=_SPECIES,
        fields="symbol,taxid,entrezgene,name",
        returnall=True,
        verbose=False,
    ).get("out", [])


class MyGeneVerifier:
    def __init__(self, cache_path: Path = _CACHE_PATH) -> None:
        self._cache_path = cache_path
        self._cache: dict[str, dict] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        if self._cache_path.exists():
            try:
                self._cache = json.loads(
                    self._cache_path.read_text(encoding="utf-8")
                )
            except Exception:
                self._cache = {}

    def save_cache(self) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(
            json.dumps(self._cache, indent=2), encoding="utf-8"
        )

    async def verify_batch(
        self,
        candidates: list[str],
        session: Any = None,  # kept for API compatibility with old verifier
    ) -> dict[str, dict]:
        """Return {token: {'verified': bool, 'symbol': str, 'species': str, 'entrez_id': int}}.

        Filters stoplist and short tokens before hitting API. Uses cache.
        """
        results: dict[str, dict] = {}
        to_query: list[str] = []

        for token in candidates:
            if not _is_valid_candidate(token):
                results[token] = {"verified": False}
                continue
            if token in self._cache:
                results[token] = self._cache[token]
            else:
                to_query.append(token)

        if not to_query:
            return results

        loop = asyncio.get_event_loop()
        try:
            hits = await loop.run_in_executor(None, _querymany_sync, to_query)
        except Exception as exc:
            logger.warning("mygene.info batch query failed: %s", exc)
            for t in to_query:
                results[t] = {"verified": False}
            return results

        found: dict[str, dict] = {}
        for hit in hits:
            if hit.get("notfound"):
                continue
            sym = hit.get("symbol", "")
            if not sym:
                continue
            query = hit.get("query", sym)
            taxid = hit.get("taxid")
            species = _taxid_to_species(taxid)
            entry = {
                "verified": True,
                "symbol": sym,
                "species": species,
                "entrez_id": hit.get("entrezgene"),
            }
            found[query] = entry
            found[sym] = entry

        for token in to_query:
            entry = found.get(token) or found.get(token.upper()) or {"verified": False}
            self._cache[token] = entry
            results[token] = entry

        return results


def _taxid_to_species(taxid: int | None) -> str:
    _MAP = {
        9606: "human",
        10090: "mouse",
        10116: "rat",
        7227: "fruitfly",
        6239: "c_elegans",
        4932: "yeast",
    }
    return _MAP.get(taxid, "other") if taxid else "unknown"

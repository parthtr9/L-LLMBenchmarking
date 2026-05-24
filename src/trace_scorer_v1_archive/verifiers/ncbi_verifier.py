"""Verify human gene symbols exist via BioThings mygene.info REST API.

Free, no API key. Rate limit ~10 req/s; we use a local cache to stay well under.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import aiohttp

logger = logging.getLogger(__name__)

_MYGENE_URL = "https://mygene.info/v3/query"
_DEFAULT_CACHE = Path("outputs/verifier_cache.json")


class NCBIVerifier:
    def __init__(self, cache_path: Path = _DEFAULT_CACHE) -> None:
        self._cache_path = cache_path
        self._cache: dict[str, bool] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        if self._cache_path.exists():
            try:
                self._cache = json.loads(self._cache_path.read_text(encoding="utf-8"))
            except Exception:
                self._cache = {}

    def save_cache(self) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(
            json.dumps(self._cache, indent=2), encoding="utf-8"
        )

    async def verify_batch(
        self, symbols: list[str], session: aiohttp.ClientSession
    ) -> dict[str, bool]:
        """Return {symbol: exists} for a list of human gene symbols.

        Uses cache; sends individual GET queries for uncached symbols.
        mygene.info free tier: ~10 req/s — add small delay between calls.
        """
        results: dict[str, bool] = {}
        to_query: list[str] = []

        for sym in symbols:
            key = f"human:{sym}"
            if key in self._cache:
                results[sym] = self._cache[key]
            else:
                to_query.append(sym)

        for sym in to_query:
            exists = await self._query_one(sym, session)
            self._cache[f"human:{sym}"] = exists
            results[sym] = exists
            await asyncio.sleep(0.12)  # ~8 req/s, stay under free-tier limit

        return results

    async def _query_one(self, symbol: str, session: aiohttp.ClientSession) -> bool:
        """GET /v3/query?q=symbol:GENE&species=human — returns True if found."""
        try:
            params = {
                "q": f"symbol:{symbol}",
                "species": "human",
                "fields": "symbol",
                "size": "1",
            }
            async with session.get(
                _MYGENE_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return False
                data = await resp.json(content_type=None)
                return bool(data.get("hits"))
        except Exception as exc:
            logger.debug("mygene.info query failed for %s: %s", symbol, exc)
            return False

    async def verify(self, symbol: str, session: aiohttp.ClientSession) -> bool:
        res = await self.verify_batch([symbol], session)
        return res.get(symbol, False)

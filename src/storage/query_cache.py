# src/storage/query_cache.py

"""In-memory query result cache with deterministic subset matching."""

import logging
import time
from dataclasses import dataclass

from src.config.settings import Settings
from src.models.product import Product

logger = logging.getLogger("ecom_search.cache")


@dataclass
class CacheEntry:
    """A cached set of results for a specific base query and filter state."""

    base_query: str
    negative_terms: frozenset[str]
    source_ids: frozenset[str]
    results: list[Product]
    timestamp: float


class QueryCache:
    """In-memory cache that exploits set-theoretic subset relationships.

    If a cached entry has fewer (or equal) negative exclusions than
    the requested query, the cached data is a *superset* of the
    requested results.  We can return the cached data and let the
    caller apply the extra negatives locally — no network needed.
    """

    def __init__(self) -> None:
        self._entries: list[CacheEntry] = []
        self._ttl: float = Settings.QUERY_CACHE_TTL

    def find_subset_match(
        self,
        base_query: str,
        requested_negatives: frozenset[str],
        source_ids: frozenset[str],
    ) -> list[Product] | None:
        """Find a cached result that covers the requested query.

        A cache hit requires:
        1. Same ``base_query`` (exact string match).
        2. Same ``source_ids`` (exact set match).
        3. Cached ``negative_terms`` is a subset of (or equal to)
           the requested negatives — meaning the cached data is
           at least as broad as what we need.

        Returns the cached product list on hit, or ``None`` on miss.
        """
        now = time.time()
        self._evict_expired(now)

        for entry in self._entries:
            if (
                entry.base_query == base_query
                and entry.source_ids == source_ids
                and entry.negative_terms.issubset(
                    requested_negatives
                )
            ):
                logger.info(
                    "Cache hit for '%s' "
                    "(cached negatives=%s, requested=%s)",
                    base_query,
                    entry.negative_terms,
                    requested_negatives,
                )
                return list(entry.results)

        return None

    def store(
        self,
        base_query: str,
        negative_terms: frozenset[str],
        source_ids: frozenset[str],
        results: list[Product],
    ) -> None:
        """Store scraped results in the cache."""
        self._entries.append(
            CacheEntry(
                base_query=base_query,
                negative_terms=negative_terms,
                source_ids=source_ids,
                results=list(results),
                timestamp=time.time(),
            )
        )
        logger.info(
            "Cached %d results for '%s' (negatives=%s)",
            len(results),
            base_query,
            negative_terms,
        )

    def clear(self) -> int:
        """Purge all cached entries.

        Returns the number of entries that were removed.
        """
        count = len(self._entries)
        self._entries.clear()
        logger.info("Cache manually purged (%d entries removed)", count)
        return count

    def _evict_expired(self, now: float) -> None:
        """Remove entries older than the TTL threshold."""
        before = len(self._entries)
        self._entries = [
            e
            for e in self._entries
            if now - e.timestamp < self._ttl
        ]
        evicted = before - len(self._entries)
        if evicted:
            logger.debug(
                "Evicted %d expired cache entries", evicted
            )

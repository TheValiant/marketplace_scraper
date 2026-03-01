# src/filters/query_enhancer.py

"""Pre-scrape query enhancement with negative keywords."""

import logging

from src.config.settings import Settings

logger = logging.getLogger("ecom_search.filters")


class QueryEnhancer:
    """Enhance search queries with negative keywords for supported platforms."""

    @staticmethod
    def enhance_query(
        query: str,
        negative_keywords: list[str],
        platform: str,
    ) -> str:
        """Append negative keywords to the query for platforms that support it.

        Platforms listed in QUERY_ENHANCED_PLATFORMS (e.g. Amazon, iHerb)
        support '-keyword' exclusion syntax in their search URLs.
        Other platforms receive the query unchanged.
        """
        if not negative_keywords:
            return query

        if platform not in Settings.QUERY_ENHANCED_PLATFORMS:
            return query

        exclusions = " ".join(
            f"-{kw}" for kw in negative_keywords if kw
        )
        enhanced = f"{query} {exclusions}"
        logger.debug(
            "Enhanced query for %s: '%s'", platform, enhanced
        )
        return enhanced

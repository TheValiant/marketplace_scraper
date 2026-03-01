# src/services/search_orchestrator.py

"""Orchestrates multi-source product searches with filtering."""

import asyncio
import importlib
import logging
from dataclasses import dataclass, field
from typing import Any

from src.config.settings import Settings
from src.filters.deduplicator import ProductDeduplicator
from src.filters.product_filter import ProductFilter
from src.filters.product_validator import ProductValidator
from src.filters.query_enhancer import QueryEnhancer
from src.models.product import Product

logger = logging.getLogger("ecom_search.orchestrator")


@dataclass
class SearchResult:
    """Container for a completed search across multiple sources."""

    query: str
    products: list[Product] = field(
        default_factory=lambda: list[Product]()
    )
    excluded_count: int = 0
    deduplicated_count: int = 0
    invalid_count: int = 0
    total_before_filter: int = 0
    errors: list[str] = field(
        default_factory=lambda: list[str]()
    )


def _load_scraper_class(dotted_path: str) -> type[Any]:
    """Dynamically import a scraper class from its dotted module path."""
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls: type[Any] = getattr(module, class_name)
    return cls


class SearchOrchestrator:
    """Coordinates scraping, query enhancement, and filtering."""

    def __init__(self) -> None:
        self.settings = Settings()

    async def search(
        self,
        query: str,
        sources: list[dict[str, str]],
        negative_keywords: list[str] | None = None,
    ) -> SearchResult:
        """Run a search across selected sources with filtering.

        Enhances the query per-platform, runs scrapers concurrently
        in threads, applies post-scrape keyword filtering, and
        returns a consolidated SearchResult.
        """
        keywords = negative_keywords or []
        result = SearchResult(query=query)

        async def run_scraper(
            scraper_path: str,
            platform_id: str,
            timeout_override: str | None = None,
        ) -> list[Product]:
            """Run a blocking scraper in a thread."""
            enhanced = QueryEnhancer.enhance_query(
                query, keywords, platform_id
            )
            scraper_cls = _load_scraper_class(scraper_path)
            scraper = scraper_cls()
            if timeout_override is not None:
                scraper._request_timeout = int(
                    timeout_override
                )
            products: list[Product] = await asyncio.to_thread(
                scraper.search, enhanced
            )
            return products

        tasks = [
            run_scraper(
                src["scraper"],
                src["id"],
                src.get("timeout"),
            )
            for src in sources
        ]

        batches = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        all_products: list[Product] = []
        for batch in batches:
            if isinstance(batch, list):
                all_products.extend(batch)
            elif isinstance(batch, Exception):
                error_msg = str(batch)
                result.errors.append(error_msg)
                logger.error(
                    "Scraper error for query '%s': %s",
                    query,
                    batch,
                    exc_info=batch,
                )

        all_products, result.invalid_count = (
            ProductValidator.validate(all_products)
        )
        result.total_before_filter = len(all_products)
        result.products, result.excluded_count = (
            ProductFilter.filter_by_keywords(
                all_products, keywords
            )
        )
        result.products, result.deduplicated_count = (
            ProductDeduplicator.deduplicate(result.products)
        )
        return result

    async def multi_search(
        self,
        raw_query: str,
        sources: list[dict[str, str]],
        negative_keywords: list[str] | None = None,
    ) -> SearchResult:
        """Run multiple semicolon-separated queries and merge results.

        Each sub-query is executed independently via ``search()``.
        Results are merged, then deduplicated across all sub-queries.
        """
        queries = [
            q.strip() for q in raw_query.split(";") if q.strip()
        ]
        if not queries:
            return SearchResult(query=raw_query)

        if len(queries) == 1:
            return await self.search(
                queries[0], sources, negative_keywords
            )

        merged = SearchResult(query=raw_query)
        all_products: list[Product] = []

        for query in queries:
            sub = await self.search(
                query, sources, negative_keywords
            )
            all_products.extend(sub.products)
            merged.excluded_count += sub.excluded_count
            merged.total_before_filter += (
                sub.total_before_filter
            )
            merged.errors.extend(sub.errors)

        # Cross-query dedup on the combined set
        merged.products, merged.deduplicated_count = (
            ProductDeduplicator.deduplicate(all_products)
        )
        return merged

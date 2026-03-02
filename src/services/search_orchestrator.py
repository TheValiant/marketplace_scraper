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
from src.filters.query_parser import (
    QueryPlanner,
    has_boolean_syntax,
    local_evaluate,
)
from src.models.product import Product
from src.storage.price_history_db import PriceHistoryDB
from src.storage.query_cache import QueryCache

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
    cache_hits: int = 0
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
        self.query_cache = QueryCache()
        self._price_db = PriceHistoryDB()

    # ── Private helpers ──────────────────────────────────

    async def _run_scrapers(
        self,
        query: str,
        sources: list[dict[str, str]],
        negative_keywords: list[str],
    ) -> tuple[list[Product], list[str]]:
        """Dispatch scrapers concurrently and collect results.

        Returns the raw product list and a list of error messages.
        """
        async def run_one(
            scraper_path: str,
            platform_id: str,
            timeout_override: str | None = None,
        ) -> list[Product]:
            enhanced = QueryEnhancer.enhance_query(
                query, negative_keywords, platform_id
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
            run_one(
                src["scraper"],
                src["id"],
                src.get("timeout"),
            )
            for src in sources
        ]

        batches = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        products: list[Product] = []
        errors: list[str] = []
        for batch in batches:
            if isinstance(batch, list):
                products.extend(batch)
            elif isinstance(batch, Exception):
                errors.append(str(batch))
                logger.error(
                    "Scraper error for query '%s': %s",
                    query,
                    batch,
                    exc_info=batch,
                )

        return products, errors

    # ── Standard search (unchanged external behaviour) ───

    async def search(
        self,
        query: str,
        sources: list[dict[str, str]],
        negative_keywords: list[str] | None = None,
    ) -> SearchResult:
        """Run a search across selected sources with filtering.

        Checks the in-memory cache first.  On a cache hit the
        scraper dispatch is skipped entirely and only the *extra*
        negative keywords are applied locally.
        """
        keywords = negative_keywords or []
        result = SearchResult(query=query)
        source_ids = frozenset(s["id"] for s in sources)
        neg_set = frozenset(keywords)

        # ── Cache probe ──────────────────────────────────
        cached = self.query_cache.find_subset_match(
            query, neg_set, source_ids
        )
        if cached is not None:
            result.cache_hits = 1
            all_products = cached
        else:
            all_products, errors = await self._run_scrapers(
                query, sources, keywords
            )
            result.errors.extend(errors)

            # Validate before caching (broadest useful data)
            all_products, result.invalid_count = (
                ProductValidator.validate(all_products)
            )

            # Store post-validation / pre-filter results
            self.query_cache.store(
                query, neg_set, source_ids, all_products
            )

            # Record price snapshots (async-safe, non-blocking)
            await asyncio.to_thread(
                self._price_db.record_snapshots,
                all_products,
            )

        # Re-validate cached data (already valid for fresh)
        if cached is not None:
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

    # ── Advanced boolean search ──────────────────────────

    async def execute_advanced_search(
        self,
        raw_query: str,
        sources: list[dict[str, str]],
        negative_keywords: list[str] | None = None,
    ) -> SearchResult:
        """Execute a boolean query with DNF expansion and AST filtering.

        1. Parse the raw query into an AST & base queries.
        2. For each base query: check cache, else scrape.
        3. Merge, validate, AST-filter, keyword-filter, deduplicate.
        """
        ui_negatives = negative_keywords or []
        plan = QueryPlanner.parse(raw_query)

        # Merge UI negatives with query-embedded negatives
        all_negatives = plan.global_negatives | set(
            ui_negatives
        )
        neg_kw_list = sorted(all_negatives)
        neg_set = frozenset(all_negatives)
        source_ids = frozenset(s["id"] for s in sources)

        result = SearchResult(query=raw_query)
        all_raw: list[Product] = []

        for bq in plan.base_queries:
            cached = self.query_cache.find_subset_match(
                bq, neg_set, source_ids
            )
            if cached is not None:
                result.cache_hits += 1
                all_raw.extend(cached)
            else:
                scraped, errors = await self._run_scrapers(
                    bq, sources, neg_kw_list
                )
                result.errors.extend(errors)

                # Validate before caching
                scraped, inv = ProductValidator.validate(
                    scraped
                )
                result.invalid_count += inv

                self.query_cache.store(
                    bq, neg_set, source_ids, scraped
                )

                # Record price snapshots
                await asyncio.to_thread(
                    self._price_db.record_snapshots,
                    scraped,
                )
                all_raw.extend(scraped)

        # Re-validate the merged set (cached entries
        # were validated at store-time)
        all_validated, extra_inv = (
            ProductValidator.validate(all_raw)
        )
        result.invalid_count += extra_inv
        result.total_before_filter = len(all_validated)

        # AST-level verification (exact boolean matching)
        ast_filtered = [
            p
            for p in all_validated
            if local_evaluate(p.title, plan.ast)
        ]
        ast_removed = len(all_validated) - len(ast_filtered)
        if ast_removed:
            logger.info(
                "AST filter removed %d non-matching products",
                ast_removed,
            )

        # Standard negative keyword filtering
        filtered, result.excluded_count = (
            ProductFilter.filter_by_keywords(
                ast_filtered, neg_kw_list
            )
        )
        # Count AST removals in the excluded tally
        result.excluded_count += ast_removed

        # Deduplication
        result.products, result.deduplicated_count = (
            ProductDeduplicator.deduplicate(filtered)
        )
        return result

    # ── Multi-search entry point ─────────────────────────

    async def multi_search(
        self,
        raw_query: str,
        sources: list[dict[str, str]],
        negative_keywords: list[str] | None = None,
    ) -> SearchResult:
        """Route the query to the appropriate search strategy.

        - Boolean syntax (AND, OR, quotes, parens) →
          ``execute_advanced_search()``.
        - Semicolon-separated multi-queries → sequential
          ``search()`` with cross-query dedup.
        - Simple single query → ``search()``.
        """
        # Boolean detection (takes priority over semicolons)
        if has_boolean_syntax(raw_query):
            return await self.execute_advanced_search(
                raw_query, sources, negative_keywords
            )

        queries = [
            q.strip()
            for q in raw_query.split(";")
            if q.strip()
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
            merged.cache_hits += sub.cache_hits
            merged.errors.extend(sub.errors)

        # Cross-query dedup on the combined set
        merged.products, merged.deduplicated_count = (
            ProductDeduplicator.deduplicate(all_products)
        )
        return merged

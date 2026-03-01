# tests/test_search_orchestrator.py

"""Tests for SearchOrchestrator integration logic."""

import unittest
from unittest.mock import patch

from src.models.product import Product
from src.services.search_orchestrator import (
    SearchOrchestrator,
    SearchResult,
)


def _make_product(title: str, source: str = "test") -> Product:
    """Create a minimal Product with the given title."""
    return Product(
        title=title, price=10.0, source=source
    )


def _fake_search(query: str) -> list[Product]:
    """Return canned products for testing."""
    return [
        _make_product("Collagen Powder", "test"),
        _make_product("Collagen Serum", "test"),
        _make_product("Collagen Gummies", "test"),
    ]


def _broken_search(query: str) -> list[Product]:
    """Simulate a scraper failure."""
    msg = "Connection timeout"
    raise ConnectionError(msg)


def _make_fake_cls() -> type[object]:
    """Build a fake scraper class returning canned products."""

    class FakeScraper:
        """Stub scraper returning canned products."""

        def search(self, query: str) -> list[Product]:
            """Delegate to module-level _fake_search."""
            return _fake_search(query)

    return FakeScraper


def _make_broken_cls() -> type[object]:
    """Build a fake scraper class that raises on search."""

    class BrokenScraper:
        """Stub scraper that raises on search."""

        def search(self, query: str) -> list[Product]:
            """Delegate to module-level _broken_search."""
            return _broken_search(query)

    return BrokenScraper


FAKE_SOURCE: list[dict[str, str]] = [
    {
        "id": "test",
        "label": "Test",
        "scraper": "fake.FakeScraper",
    },
]

BAD_SOURCE: list[dict[str, str]] = [
    {
        "id": "bad",
        "label": "Bad",
        "scraper": "fake.BrokenScraper",
    },
]

LOAD_PATH = (
    "src.services.search_orchestrator._load_scraper_class"
)


class TestSearchOrchestrator(unittest.IsolatedAsyncioTestCase):
    """SearchOrchestrator.search integration tests."""

    @patch(LOAD_PATH, return_value=_make_fake_cls())
    async def test_returns_search_result(
        self, _mock_load: object,
    ) -> None:
        """search() returns a SearchResult dataclass."""
        orch = SearchOrchestrator()
        result = await orch.search("collagen", FAKE_SOURCE)
        self.assertIsInstance(result, SearchResult)
        self.assertEqual(result.query, "collagen")

    @patch(LOAD_PATH, return_value=_make_fake_cls())
    async def test_collects_products(
        self, _mock_load: object,
    ) -> None:
        """Products from all sources are collected."""
        orch = SearchOrchestrator()
        result = await orch.search("collagen", FAKE_SOURCE)
        self.assertEqual(len(result.products), 3)

    @patch(LOAD_PATH, return_value=_make_fake_cls())
    async def test_post_filter_excludes(
        self, _mock_load: object,
    ) -> None:
        """Negative keywords filter products after scraping."""
        orch = SearchOrchestrator()
        result = await orch.search(
            "collagen", FAKE_SOURCE, ["serum", "gummies"]
        )
        self.assertEqual(len(result.products), 1)
        self.assertEqual(
            result.products[0].title, "Collagen Powder"
        )
        self.assertEqual(result.excluded_count, 2)
        self.assertEqual(result.total_before_filter, 3)

    @patch(LOAD_PATH, return_value=_make_fake_cls())
    async def test_no_filter_no_exclusions(
        self, _mock_load: object,
    ) -> None:
        """Without negative keywords, nothing is excluded."""
        orch = SearchOrchestrator()
        result = await orch.search("collagen", FAKE_SOURCE)
        self.assertEqual(result.excluded_count, 0)
        self.assertEqual(result.total_before_filter, 3)

    @patch(LOAD_PATH, return_value=_make_broken_cls())
    async def test_scraper_exception_captured(
        self, _mock_load: object,
    ) -> None:
        """Scraper exceptions are captured in result.errors."""
        orch = SearchOrchestrator()
        result = await orch.search("collagen", BAD_SOURCE)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(len(result.products), 0)

    async def test_empty_sources_returns_empty(self) -> None:
        """No sources selected returns empty result."""
        orch = SearchOrchestrator()
        result = await orch.search("collagen", [])
        self.assertEqual(len(result.products), 0)
        self.assertEqual(result.excluded_count, 0)


class TestMultiSearch(unittest.IsolatedAsyncioTestCase):
    """SearchOrchestrator.multi_search integration tests."""

    @patch(LOAD_PATH, return_value=_make_fake_cls())
    async def test_single_query_no_semicolon(
        self, _mock_load: object,
    ) -> None:
        """A query without semicolons behaves like search()."""
        orch = SearchOrchestrator()
        result = await orch.multi_search(
            "collagen", FAKE_SOURCE
        )
        self.assertEqual(result.query, "collagen")
        self.assertEqual(len(result.products), 3)

    @patch(LOAD_PATH, return_value=_make_fake_cls())
    async def test_multi_query_merges_products(
        self, _mock_load: object,
    ) -> None:
        """Semicolon-separated queries merge products from all sub-queries."""
        orch = SearchOrchestrator()
        result = await orch.multi_search(
            "collagen;vitamin d", FAKE_SOURCE
        )
        self.assertEqual(result.query, "collagen;vitamin d")
        # Each sub-query returns 3 products, but dedup may merge
        # same-title/same-source duplicates. At minimum, merged > single.
        self.assertGreaterEqual(
            result.total_before_filter, 6
        )

    @patch(LOAD_PATH, return_value=_make_broken_cls())
    async def test_multi_query_aggregates_errors(
        self, _mock_load: object,
    ) -> None:
        """Errors from multiple sub-queries are collected."""
        orch = SearchOrchestrator()
        result = await orch.multi_search(
            "collagen;vitamin d", BAD_SOURCE
        )
        self.assertEqual(len(result.errors), 2)
        self.assertEqual(len(result.products), 0)

    async def test_empty_query_returns_empty(self) -> None:
        """An empty query returns an empty SearchResult."""
        orch = SearchOrchestrator()
        result = await orch.multi_search("", FAKE_SOURCE)
        self.assertEqual(len(result.products), 0)
        self.assertEqual(result.query, "")

    @patch(LOAD_PATH, return_value=_make_fake_cls())
    async def test_whitespace_segments_skipped(
        self, _mock_load: object,
    ) -> None:
        """Empty segments between semicolons are ignored."""
        orch = SearchOrchestrator()
        result = await orch.multi_search(
            "collagen ; ; vitamin", FAKE_SOURCE
        )
        # Only 2 valid sub-queries: "collagen" and "vitamin"
        self.assertGreaterEqual(
            result.total_before_filter, 6
        )


class TestSearchOrchestratorCache(
    unittest.IsolatedAsyncioTestCase
):
    """Cache interaction tests for SearchOrchestrator."""

    @patch(LOAD_PATH, return_value=_make_fake_cls())
    async def test_cache_hit_skips_scrapers(
        self, mock_load: object,
    ) -> None:
        """A cache hit means scrapers are NOT called a second time."""
        orch = SearchOrchestrator()
        # First search → cache miss → scrapers called
        await orch.search("collagen", FAKE_SOURCE)

        # Second identical search → cache hit
        result2 = await orch.search("collagen", FAKE_SOURCE)
        self.assertEqual(result2.cache_hits, 1)

    @patch(LOAD_PATH, return_value=_make_fake_cls())
    async def test_cache_stores_after_scrape(
        self, _mock_load: object,
    ) -> None:
        """After a scrape, results are stored in the cache."""
        orch = SearchOrchestrator()
        await orch.search("collagen", FAKE_SOURCE)

        cached = orch.query_cache.find_subset_match(
            "collagen",
            frozenset(),
            frozenset({"test"}),
        )
        self.assertIsNotNone(cached)

    @patch(LOAD_PATH, return_value=_make_fake_cls())
    async def test_cache_clear_forces_rescrape(
        self, mock_load: object,
    ) -> None:
        """After invalidation, next search re-scrapes."""
        orch = SearchOrchestrator()
        await orch.search("collagen", FAKE_SOURCE)
        orch.query_cache.clear()

        result2 = await orch.search("collagen", FAKE_SOURCE)
        # Cache was cleared, so this is a miss (cache_hits=0)
        self.assertEqual(result2.cache_hits, 0)

    @patch(LOAD_PATH, return_value=_make_fake_cls())
    async def test_cache_subset_negatives_hit(
        self, _mock_load: object,
    ) -> None:
        """A broader cached result serves a narrower negative query."""
        orch = SearchOrchestrator()
        # Cache with no negatives
        await orch.search("collagen", FAKE_SOURCE)

        # Narrower query (with negatives) should hit the cache
        result = await orch.search(
            "collagen", FAKE_SOURCE, ["serum"]
        )
        self.assertEqual(result.cache_hits, 1)

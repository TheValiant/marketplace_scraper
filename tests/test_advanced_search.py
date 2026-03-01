# tests/test_advanced_search.py

"""Integration tests for advanced boolean search and caching in the orchestrator."""

import unittest
from unittest.mock import patch

from src.models.product import Product
from src.services.search_orchestrator import (
    SearchOrchestrator,
    SearchResult,
)


def _p(
    title: str, price: float = 10.0, source: str = "test"
) -> Product:
    """Create a minimal Product."""
    return Product(title=title, price=price, source=source)


PRODUCTS_COLLAGEN = [
    _p("Multi Collagen Powder"),
    _p("Collagen Serum"),
    _p("Multi Collagen Peptides"),
    _p("Types I II III V X Collagen"),
]

PRODUCTS_VITAMIN = [
    _p("Vitamin D 5000 IU"),
    _p("Vitamin C Powder"),
]

LOAD_PATH = (
    "src.services.search_orchestrator._load_scraper_class"
)


def _make_scraper_cls(
    products: list[Product],
) -> type[object]:
    """Build a fake scraper class returning the given products."""

    class FakeScraper:
        """Stub that returns the given products."""

        _products = products

        def search(self, query: str) -> list[Product]:
            """Return the configured products."""
            return list(self._products)

    return FakeScraper


FAKE_SOURCE: list[dict[str, str]] = [
    {
        "id": "test",
        "label": "Test",
        "scraper": "fake.FakeScraper",
    },
]


# ── Cache integration ────────────────────────────────────


class TestCacheIntegration(unittest.IsolatedAsyncioTestCase):
    """Verify the cache skips scraper dispatch on hits."""

    @patch(
        LOAD_PATH,
        return_value=_make_scraper_cls(PRODUCTS_COLLAGEN),
    )
    async def test_second_search_uses_cache(
        self, mock_load: object,
    ) -> None:
        """Repeating the same search returns cached results."""
        orch = SearchOrchestrator()

        first = await orch.search(
            "collagen", FAKE_SOURCE
        )
        self.assertEqual(first.cache_hits, 0)
        self.assertGreater(len(first.products), 0)

        second = await orch.search(
            "collagen", FAKE_SOURCE
        )
        self.assertEqual(second.cache_hits, 1)
        self.assertGreater(len(second.products), 0)

    @patch(
        LOAD_PATH,
        return_value=_make_scraper_cls(PRODUCTS_COLLAGEN),
    )
    async def test_subset_negatives_hit_cache(
        self, mock_load: object,
    ) -> None:
        """Broader cached query serves subset with extra negatives."""
        orch = SearchOrchestrator()

        # First search: no negatives
        await orch.search("collagen", FAKE_SOURCE)

        # Second search: with negatives — should hit cache
        result = await orch.search(
            "collagen", FAKE_SOURCE, ["serum"]
        )
        self.assertEqual(result.cache_hits, 1)
        for p in result.products:
            self.assertNotIn("serum", p.title.lower())

    @patch(
        LOAD_PATH,
        return_value=_make_scraper_cls(PRODUCTS_COLLAGEN),
    )
    async def test_different_sources_miss_cache(
        self, mock_load: object,
    ) -> None:
        """Adding a source forces a cache miss."""
        orch = SearchOrchestrator()

        await orch.search("collagen", FAKE_SOURCE)

        different_sources: list[dict[str, str]] = [
            {
                "id": "test",
                "label": "Test",
                "scraper": "fake.FakeScraper",
            },
            {
                "id": "other",
                "label": "Other",
                "scraper": "fake.FakeScraper",
            },
        ]
        result = await orch.search(
            "collagen", different_sources
        )
        self.assertEqual(result.cache_hits, 0)


# ── Advanced boolean search ──────────────────────────────


class TestAdvancedBooleanSearch(
    unittest.IsolatedAsyncioTestCase,
):
    """Verify boolean queries route through the advanced pipeline."""

    @patch(
        LOAD_PATH,
        return_value=_make_scraper_cls(PRODUCTS_COLLAGEN),
    )
    async def test_or_query_dispatches_multiple(
        self, mock_load: object,
    ) -> None:
        """OR query produces multiple base queries."""
        orch = SearchOrchestrator()
        result = await orch.multi_search(
            '"multi collagen" OR "types I II III"',
            FAKE_SOURCE,
        )
        self.assertIsInstance(result, SearchResult)
        self.assertGreater(len(result.products), 0)

    @patch(
        LOAD_PATH,
        return_value=_make_scraper_cls(PRODUCTS_COLLAGEN),
    )
    async def test_ast_filter_removes_non_matching(
        self, mock_load: object,
    ) -> None:
        """AST filter drops products that don't satisfy the boolean."""
        orch = SearchOrchestrator()
        # Only "Multi Collagen" products should survive
        result = await orch.multi_search(
            '"multi collagen"', FAKE_SOURCE
        )
        for p in result.products:
            self.assertIn(
                "multi collagen", p.title.lower()
            )

    @patch(
        LOAD_PATH,
        return_value=_make_scraper_cls(PRODUCTS_COLLAGEN),
    )
    async def test_negatives_in_boolean_query(
        self, mock_load: object,
    ) -> None:
        """Embedded negatives are applied after AST filtering."""
        orch = SearchOrchestrator()
        result = await orch.multi_search(
            '"multi collagen" -peptides', FAKE_SOURCE
        )
        for p in result.products:
            self.assertNotIn("peptides", p.title.lower())

    @patch(
        LOAD_PATH,
        return_value=_make_scraper_cls(PRODUCTS_COLLAGEN),
    )
    async def test_and_query_filters_strictly(
        self, mock_load: object,
    ) -> None:
        """AND query requires all terms present."""
        orch = SearchOrchestrator()
        result = await orch.multi_search(
            '"multi collagen" AND powder', FAKE_SOURCE
        )
        for p in result.products:
            title = p.title.lower()
            self.assertIn("multi collagen", title)
            self.assertIn("powder", title)


# ── Backward compatibility ───────────────────────────────


class TestBackwardCompat(unittest.IsolatedAsyncioTestCase):
    """Ensure simple and semicolon queries still work."""

    @patch(
        LOAD_PATH,
        return_value=_make_scraper_cls(PRODUCTS_COLLAGEN),
    )
    async def test_simple_query_unchanged(
        self, mock_load: object,
    ) -> None:
        """A plain query without boolean syntax uses standard search."""
        orch = SearchOrchestrator()
        result = await orch.multi_search(
            "collagen", FAKE_SOURCE
        )
        self.assertIsInstance(result, SearchResult)
        self.assertEqual(result.query, "collagen")

    @patch(
        LOAD_PATH,
        return_value=_make_scraper_cls(PRODUCTS_COLLAGEN),
    )
    async def test_semicolon_query_unchanged(
        self, mock_load: object,
    ) -> None:
        """Semicolon-separated queries use the standard multi-search path."""
        orch = SearchOrchestrator()
        result = await orch.multi_search(
            "collagen;vitamin", FAKE_SOURCE
        )
        self.assertIsInstance(result, SearchResult)
        self.assertEqual(result.query, "collagen;vitamin")

    async def test_empty_query_returns_empty(self) -> None:
        """Empty query returns empty SearchResult."""
        orch = SearchOrchestrator()
        result = await orch.multi_search("", FAKE_SOURCE)
        self.assertEqual(len(result.products), 0)


# ── Cache + advanced search interaction ──────────────────


class TestAdvancedCacheInteraction(
    unittest.IsolatedAsyncioTestCase,
):
    """Verify caching works within advanced boolean searches."""

    @patch(
        LOAD_PATH,
        return_value=_make_scraper_cls(PRODUCTS_COLLAGEN),
    )
    async def test_repeated_boolean_uses_cache(
        self, mock_load: object,
    ) -> None:
        """Second identical boolean search hits cache."""
        orch = SearchOrchestrator()

        first = await orch.multi_search(
            '"multi collagen"', FAKE_SOURCE
        )
        second = await orch.multi_search(
            '"multi collagen"', FAKE_SOURCE
        )
        self.assertGreater(second.cache_hits, 0)
        self.assertEqual(
            len(first.products), len(second.products)
        )

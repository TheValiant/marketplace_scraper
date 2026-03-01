# tests/test_query_cache.py

"""Tests for the in-memory deterministic subset cache."""

import time
import unittest
from unittest.mock import patch

from src.models.product import Product
from src.storage.query_cache import QueryCache


def _p(title: str, source: str = "amazon") -> Product:
    """Create a minimal Product for testing."""
    return Product(title=title, price=10.0, source=source)


class TestQueryCache(unittest.TestCase):
    """QueryCache unit tests."""

    def setUp(self) -> None:
        self.cache = QueryCache()

    # ── Store & retrieve ─────────────────────────────────

    def test_exact_match_hit(self) -> None:
        """Same query, same negatives, same sources → hit."""
        products = [_p("Collagen Powder")]
        self.cache.store(
            "collagen",
            frozenset({"mask"}),
            frozenset({"amazon"}),
            products,
        )
        result = self.cache.find_subset_match(
            "collagen",
            frozenset({"mask"}),
            frozenset({"amazon"}),
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0].title, "Collagen Powder"
        )

    def test_subset_negatives_hit(self) -> None:
        """Cached has fewer negatives than requested → hit."""
        products = [_p("Collagen Powder"), _p("Collagen Serum")]
        self.cache.store(
            "collagen",
            frozenset({"mask"}),
            frozenset({"amazon"}),
            products,
        )
        # Request has more negatives (mask + serum)
        result = self.cache.find_subset_match(
            "collagen",
            frozenset({"mask", "serum"}),
            frozenset({"amazon"}),
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 2)

    def test_empty_cached_negatives_hit(self) -> None:
        """Cached with no negatives covers any negative set."""
        products = [_p("A"), _p("B")]
        self.cache.store(
            "collagen",
            frozenset(),
            frozenset({"amazon"}),
            products,
        )
        result = self.cache.find_subset_match(
            "collagen",
            frozenset({"mask", "serum"}),
            frozenset({"amazon"}),
        )
        self.assertIsNotNone(result)

    def test_superset_negatives_miss(self) -> None:
        """Cached has MORE negatives than requested → miss."""
        products = [_p("A")]
        self.cache.store(
            "collagen",
            frozenset({"mask", "serum"}),
            frozenset({"amazon"}),
            products,
        )
        # Request asks for fewer negatives — cached data
        # was filtered too aggressively to reuse.
        result = self.cache.find_subset_match(
            "collagen",
            frozenset({"mask"}),
            frozenset({"amazon"}),
        )
        self.assertIsNone(result)

    def test_different_query_miss(self) -> None:
        """Different base query → miss."""
        self.cache.store(
            "collagen",
            frozenset(),
            frozenset({"amazon"}),
            [_p("X")],
        )
        result = self.cache.find_subset_match(
            "vitamin",
            frozenset(),
            frozenset({"amazon"}),
        )
        self.assertIsNone(result)

    def test_different_sources_miss(self) -> None:
        """Different source set → miss."""
        self.cache.store(
            "collagen",
            frozenset(),
            frozenset({"amazon"}),
            [_p("X")],
        )
        result = self.cache.find_subset_match(
            "collagen",
            frozenset(),
            frozenset({"amazon", "noon"}),
        )
        self.assertIsNone(result)

    def test_empty_cache_miss(self) -> None:
        """Empty cache always misses."""
        result = self.cache.find_subset_match(
            "collagen",
            frozenset(),
            frozenset({"amazon"}),
        )
        self.assertIsNone(result)

    # ── TTL expiration ───────────────────────────────────

    def test_expired_entry_evicted(self) -> None:
        """Entries past TTL are evicted and not returned."""
        self.cache.store(
            "collagen",
            frozenset(),
            frozenset({"amazon"}),
            [_p("X")],
        )
        # Advance time past TTL
        future = time.time() + 4000
        with patch("src.storage.query_cache.time.time", return_value=future):
            result = self.cache.find_subset_match(
                "collagen",
                frozenset(),
                frozenset({"amazon"}),
            )
        self.assertIsNone(result)

    # ── Result isolation ─────────────────────────────────

    def test_returns_copy_not_reference(self) -> None:
        """Returned list is a copy — mutations don't corrupt cache."""
        products = [_p("Original")]
        self.cache.store(
            "q",
            frozenset(),
            frozenset({"a"}),
            products,
        )
        result = self.cache.find_subset_match(
            "q", frozenset(), frozenset({"a"})
        )
        assert result is not None
        result.append(_p("Extra"))

        second = self.cache.find_subset_match(
            "q", frozenset(), frozenset({"a"})
        )
        assert second is not None
        self.assertEqual(len(second), 1)

    # ── clear() ──────────────────────────────────────────

    def test_clear_empties_all_entries(self) -> None:
        """clear() removes every cached entry."""
        self.cache.store(
            "a", frozenset(), frozenset({"x"}), [_p("A")]
        )
        self.cache.store(
            "b", frozenset(), frozenset({"x"}), [_p("B")]
        )
        self.cache.clear()
        result = self.cache.find_subset_match(
            "a", frozenset(), frozenset({"x"})
        )
        self.assertIsNone(result)

    def test_clear_on_empty_cache_returns_zero(self) -> None:
        """clear() on empty cache returns 0."""
        count = self.cache.clear()
        self.assertEqual(count, 0)

    def test_clear_returns_purged_count(self) -> None:
        """clear() returns the number of entries removed."""
        self.cache.store(
            "a", frozenset(), frozenset({"x"}), [_p("A")]
        )
        self.cache.store(
            "b", frozenset(), frozenset({"x"}), [_p("B")]
        )
        count = self.cache.clear()
        self.assertEqual(count, 2)

    def test_find_returns_none_after_clear(self) -> None:
        """After clear(), previously cached queries miss."""
        self.cache.store(
            "collagen",
            frozenset(),
            frozenset({"amazon"}),
            [_p("X")],
        )
        self.cache.clear()
        result = self.cache.find_subset_match(
            "collagen",
            frozenset(),
            frozenset({"amazon"}),
        )
        self.assertIsNone(result)

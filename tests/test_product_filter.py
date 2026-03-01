# tests/test_product_filter.py

"""Tests for ProductFilter post-scrape keyword filtering."""

import unittest

from src.filters.product_filter import ProductFilter
from src.models.product import Product


def _make_product(title: str) -> Product:
    """Create a minimal Product with the given title."""
    return Product(
        title=title, price=10.0, source="test"
    )


class TestFilterByKeywords(unittest.TestCase):
    """ProductFilter.filter_by_keywords behaviour."""

    def test_empty_keywords_returns_all(self) -> None:
        """No keywords means no filtering."""
        products = [_make_product("Alpha"), _make_product("Beta")]
        kept, excluded = ProductFilter.filter_by_keywords(
            products, []
        )
        self.assertEqual(len(kept), 2)
        self.assertEqual(excluded, 0)

    def test_single_keyword_excludes_match(self) -> None:
        """A product whose title contains the keyword is excluded."""
        products = [
            _make_product("Collagen Serum"),
            _make_product("Collagen Powder"),
        ]
        kept, excluded = ProductFilter.filter_by_keywords(
            products, ["serum"]
        )
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].title, "Collagen Powder")
        self.assertEqual(excluded, 1)

    def test_case_insensitive(self) -> None:
        """Keyword matching is case-insensitive."""
        products = [_make_product("NIGHT CREAM")]
        kept, excluded = ProductFilter.filter_by_keywords(
            products, ["cream"]
        )
        self.assertEqual(len(kept), 0)
        self.assertEqual(excluded, 1)

    def test_multiple_keywords(self) -> None:
        """All keywords are checked (OR logic)."""
        products = [
            _make_product("Serum X"),
            _make_product("Mask Y"),
            _make_product("Powder Z"),
        ]
        kept, excluded = ProductFilter.filter_by_keywords(
            products, ["serum", "mask"]
        )
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].title, "Powder Z")
        self.assertEqual(excluded, 2)

    def test_no_match_returns_all(self) -> None:
        """When no product matches, all are kept."""
        products = [
            _make_product("Collagen Peptides"),
            _make_product("Bone Broth Protein"),
        ]
        kept, excluded = ProductFilter.filter_by_keywords(
            products, ["gummies"]
        )
        self.assertEqual(len(kept), 2)
        self.assertEqual(excluded, 0)

    def test_empty_products_list(self) -> None:
        """An empty input list returns empty output."""
        kept, excluded = ProductFilter.filter_by_keywords(
            [], ["serum"]
        )
        self.assertEqual(len(kept), 0)
        self.assertEqual(excluded, 0)

    def test_substring_match(self) -> None:
        """Keywords match as substrings within the title."""
        products = [_make_product("Anti-aging Serum for Face")]
        _kept, excluded = ProductFilter.filter_by_keywords(
            products, ["serum"]
        )
        self.assertEqual(excluded, 1)

    def test_all_excluded(self) -> None:
        """When every product matches, all are excluded."""
        products = [
            _make_product("Serum A"),
            _make_product("Serum B"),
        ]
        kept, excluded = ProductFilter.filter_by_keywords(
            products, ["serum"]
        )
        self.assertEqual(len(kept), 0)
        self.assertEqual(excluded, 2)

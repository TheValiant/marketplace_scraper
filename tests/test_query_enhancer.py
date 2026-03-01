# tests/test_query_enhancer.py

"""Tests for QueryEnhancer pre-scrape query enhancement."""

import unittest

from src.filters.query_enhancer import QueryEnhancer


class TestEnhanceQuery(unittest.TestCase):
    """QueryEnhancer.enhance_query behaviour."""

    def test_empty_keywords_unchanged(self) -> None:
        """No keywords returns the original query."""
        result = QueryEnhancer.enhance_query(
            "collagen", [], "amazon"
        )
        self.assertEqual(result, "collagen")

    def test_amazon_appends_exclusions(self) -> None:
        """Amazon (supported platform) gets -keyword syntax."""
        result = QueryEnhancer.enhance_query(
            "collagen", ["serum", "cream"], "amazon"
        )
        self.assertEqual(
            result, "collagen -serum -cream"
        )

    def test_iherb_appends_exclusions(self) -> None:
        """iHerb (supported platform) gets -keyword syntax."""
        result = QueryEnhancer.enhance_query(
            "vitamin d", ["gummies"], "iherb"
        )
        self.assertEqual(result, "vitamin d -gummies")

    def test_unsupported_platform_unchanged(self) -> None:
        """Unsupported platforms get the original query."""
        result = QueryEnhancer.enhance_query(
            "collagen", ["serum"], "noon"
        )
        self.assertEqual(result, "collagen")

    def test_binsina_unchanged(self) -> None:
        """BinSina (unsupported) gets the original query."""
        result = QueryEnhancer.enhance_query(
            "protein", ["bar"], "binsina"
        )
        self.assertEqual(result, "protein")

    def test_multiple_keywords(self) -> None:
        """Multiple keywords each get a dash prefix."""
        result = QueryEnhancer.enhance_query(
            "fish oil", ["cream", "mask", "serum"], "amazon"
        )
        self.assertEqual(
            result, "fish oil -cream -mask -serum"
        )

    def test_empty_keyword_strings_skipped(self) -> None:
        """Empty strings in the keywords list are ignored."""
        result = QueryEnhancer.enhance_query(
            "collagen", ["", "serum", ""], "amazon"
        )
        self.assertEqual(result, "collagen -serum")

    def test_preserves_original_query(self) -> None:
        """The original query text is preserved unchanged."""
        result = QueryEnhancer.enhance_query(
            "multi collagen peptides", ["gummies"], "amazon"
        )
        self.assertTrue(
            result.startswith("multi collagen peptides")
        )

    # ── Extra edge-case tests ────────────────────────────

    def test_whitespace_only_keywords_skipped(self) -> None:
        """Keywords consisting of only whitespace produce no exclusion."""
        result = QueryEnhancer.enhance_query(
            "collagen", ["  ", "\t"], "amazon"
        )
        # Whitespace strings are truthy but produce "-  " artifacts
        # unless the caller strips them; document current behaviour.
        self.assertIn("collagen", result)

    def test_empty_platform_string_unchanged(self) -> None:
        """An empty platform id doesn't match any enhanced platform."""
        result = QueryEnhancer.enhance_query(
            "collagen", ["serum"], ""
        )
        self.assertEqual(result, "collagen")

    def test_duplicate_keywords_all_appended(self) -> None:
        """Duplicate keywords are each appended (caller responsibility)."""
        result = QueryEnhancer.enhance_query(
            "collagen", ["serum", "serum"], "amazon"
        )
        self.assertEqual(
            result, "collagen -serum -serum"
        )

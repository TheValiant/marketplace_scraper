# tests/test_settings.py

"""Tests for the Settings configuration class."""

import unittest
from pathlib import Path

from src.config.settings import Settings


class TestSettings(unittest.TestCase):
    """Verify Settings constants and source registry."""

    def test_request_delay_is_positive_float(self) -> None:
        """REQUEST_DELAY must be a positive number."""
        self.assertIsInstance(Settings.REQUEST_DELAY, float)
        self.assertGreater(Settings.REQUEST_DELAY, 0)

    def test_request_timeout_is_positive_int(self) -> None:
        """REQUEST_TIMEOUT must be a positive integer."""
        self.assertIsInstance(Settings.REQUEST_TIMEOUT, int)
        self.assertGreater(Settings.REQUEST_TIMEOUT, 0)

    def test_max_retries_is_positive(self) -> None:
        """MAX_RETRIES must be >= 1."""
        self.assertGreaterEqual(Settings.MAX_RETRIES, 1)

    def test_circuit_breaker_threshold_positive(self) -> None:
        """CIRCUIT_BREAKER_THRESHOLD must be >= 1."""
        self.assertGreaterEqual(
            Settings.CIRCUIT_BREAKER_THRESHOLD, 1
        )

    def test_query_cache_ttl_positive(self) -> None:
        """QUERY_CACHE_TTL must be > 0."""
        self.assertGreater(Settings.QUERY_CACHE_TTL, 0)

    def test_available_sources_has_six(self) -> None:
        """Registry must contain exactly 6 sources."""
        self.assertEqual(
            len(Settings.AVAILABLE_SOURCES), 6
        )

    def test_each_source_has_required_keys(self) -> None:
        """Every source must have id, label, and scraper keys."""
        for src in Settings.AVAILABLE_SOURCES:
            with self.subTest(src=src.get("id", "?")):
                self.assertIn("id", src)
                self.assertIn("label", src)
                self.assertIn("scraper", src)

    def test_source_ids_are_unique(self) -> None:
        """No duplicate source ids."""
        ids = [s["id"] for s in Settings.AVAILABLE_SOURCES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_query_enhanced_platforms_subset_of_sources(self) -> None:
        """Every enhanced platform must be a registered source."""
        source_ids = {
            s["id"] for s in Settings.AVAILABLE_SOURCES
        }
        for platform in Settings.QUERY_ENHANCED_PLATFORMS:
            self.assertIn(platform, source_ids)

    def test_path_constants_are_paths(self) -> None:
        """Path-typed settings are Path instances."""
        self.assertIsInstance(Settings.BASE_DIR, Path)
        self.assertIsInstance(
            Settings.SELECTORS_PATH, Path
        )
        self.assertIsInstance(Settings.RESULTS_DIR, Path)
        self.assertIsInstance(Settings.LOGS_DIR, Path)

    def test_selectors_path_exists(self) -> None:
        """The selectors.json file must exist on disk."""
        self.assertTrue(Settings.SELECTORS_PATH.exists())

    def test_impersonate_browser_is_string(self) -> None:
        """IMPERSONATE_BROWSER must be a non-empty string."""
        self.assertIsInstance(
            Settings.IMPERSONATE_BROWSER, str
        )
        self.assertTrue(len(Settings.IMPERSONATE_BROWSER) > 0)

    def test_default_headers_has_accept_language(self) -> None:
        """DEFAULT_HEADERS must include Accept-Language."""
        self.assertIn(
            "Accept-Language", Settings.DEFAULT_HEADERS
        )


if __name__ == "__main__":
    unittest.main()

# tests/test_health_checker.py

"""Tests for the scraper health checker service."""

import unittest
from unittest.mock import MagicMock, patch

from src.services.health_checker import (
    HealthChecker,
    HealthResult,
    probe_source,
)


class TestProbeSource(unittest.TestCase):
    """Tests for the per-source health probe function."""

    def _make_source(
        self,
        source_id: str = "noon",
        scraper_path: str = "src.scrapers.noon_scraper.NoonScraper",
    ) -> dict[str, str]:
        """Build a minimal source config dict."""
        return {"id": source_id, "scraper": scraper_path}

    @patch("src.services.health_checker.importlib")
    def test_ok_status(self, mock_importlib: MagicMock) -> None:
        """A fast 200 response should return 'ok' status."""
        mock_scraper = MagicMock()
        mock_scraper._get_homepage.return_value = "https://noon.com"
        mock_scraper.settings = MagicMock()
        mock_scraper.settings.DEFAULT_HEADERS = {}

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_scraper.session.get.return_value = mock_resp

        mock_cls = MagicMock(return_value=mock_scraper)
        mock_importlib.import_module.return_value = MagicMock(
            NoonScraper=mock_cls,
        )

        result = probe_source(self._make_source())
        self.assertEqual(result.status, "ok")
        self.assertGreater(result.latency_ms, 0)

    @patch("src.services.health_checker.importlib")
    def test_down_on_http_error(
        self, mock_importlib: MagicMock,
    ) -> None:
        """A non-200 response should return 'down' status."""
        mock_scraper = MagicMock()
        mock_scraper._get_homepage.return_value = "https://noon.com"
        mock_scraper.settings = MagicMock()
        mock_scraper.settings.DEFAULT_HEADERS = {}

        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_scraper.session.get.return_value = mock_resp

        mock_cls = MagicMock(return_value=mock_scraper)
        mock_importlib.import_module.return_value = MagicMock(
            NoonScraper=mock_cls,
        )

        result = probe_source(self._make_source())
        self.assertEqual(result.status, "down")
        self.assertIn("403", result.message)

    @patch("src.services.health_checker.importlib")
    def test_down_on_exception(
        self, mock_importlib: MagicMock,
    ) -> None:
        """A network error should return 'down' status."""
        mock_scraper = MagicMock()
        mock_scraper._get_homepage.return_value = "https://noon.com"
        mock_scraper.settings = MagicMock()
        mock_scraper.settings.DEFAULT_HEADERS = {}
        mock_scraper.session.get.side_effect = ConnectionError(
            "Connection refused",
        )

        mock_cls = MagicMock(return_value=mock_scraper)
        mock_importlib.import_module.return_value = MagicMock(
            NoonScraper=mock_cls,
        )

        result = probe_source(self._make_source())
        self.assertEqual(result.status, "down")
        self.assertIn("Connection refused", result.message)

    def test_down_on_bad_scraper_path(self) -> None:
        """An invalid scraper path should return 'down'."""
        source = self._make_source(
            scraper_path="nonexistent.module.BadClass",
        )
        result = probe_source(source)
        self.assertEqual(result.status, "down")
        self.assertIn("Failed to load", result.message)


class TestHealthChecker(unittest.IsolatedAsyncioTestCase):
    """Tests for the HealthChecker orchestrator."""

    @patch("src.services.health_checker.probe_source")
    async def test_check_all_returns_all_sources(
        self, mock_probe: MagicMock,
    ) -> None:
        """check_all should return one result per source."""
        mock_probe.return_value = HealthResult(
            source_id="test",
            status="ok",
            latency_ms=100.0,
            message="",
        )

        checker = HealthChecker()
        results = await checker.check_all()

        self.assertEqual(
            len(results), len(checker.sources),
        )


if __name__ == "__main__":
    unittest.main()
